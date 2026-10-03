import mysql from 'mysql2/promise';
import dotenv from 'dotenv';
import axios from 'axios';
import * as uuid from 'uuid';
import ytdl from '@distube/ytdl-core';
import * as fs from 'fs';
import * as path from 'path';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { GoogleAIFileManager } from '@google/generative-ai/server';

dotenv.config();

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const fileManager = new GoogleAIFileManager(process.env.GEMINI_API_KEY!);

interface Post {
  id: string;
  source: string;
  type: string;
  identifier: string;
  metadata: any;
  summary?: string;
  user_id?: string;
  title?: string;
}

interface Timestamp {
  time: string;
  description: string;
}

interface ChunkSegment {
  index: number;
  startTime: number;  // 秒
  endTime: number;    // 秒
  charLimit: number;
  isFirstChunk: boolean;
  type: 'mechanical';
}

// 定数定義
const CHUNK_DURATION_SECONDS = 180;  // 1チャンクの長さ（3分 = 180秒）
const BASE_CHAR_LIMIT = 2400;        // チャンクあたりの基準最大文字数
const HARD_LIMIT_TOTAL = 24000;      // 動画全体のハードリミット文字数

/**
 * 時間文字列（MM:SS または HH:MM:SS）を秒に変換
 */
function timeStringToSeconds(timeStr: string): number {
  const parts = timeStr.split(':').map(p => parseInt(p));
  if (parts.length === 3) {
    // HH:MM:SS
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    // MM:SS
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

/**
 * 機械的分割のみ: 動的ステップ計算による時間ベース分割
 */
function calculateMechanicalSegments(
  durationSeconds: number
): ChunkSegment[] {
  // 180秒未満の動画は分割不要
  if (durationSeconds <= CHUNK_DURATION_SECONDS) {
    return [];
  }

  console.log(`  ⚙️  Using mechanical time-based segmentation`);

  // 動的ステップ計算: (合計時間(分) ÷ 30) × 3分
  const durationMinutes = durationSeconds / 60;
  let stepMinutes = (durationMinutes / 30) * 3;

  // 最低3分、最大10分のステップに制限
  stepMinutes = Math.max(3, Math.min(stepMinutes, 10));
  const stepSeconds = Math.round(stepMinutes * 60);

  console.log(`  📊 Dynamic step: ${stepMinutes.toFixed(1)} min (total: ${durationMinutes.toFixed(1)} min)`);

  const totalSegments = Math.ceil(durationSeconds / stepSeconds);

  // 各セグメントで「600文字 × 4チャンク」を生成 = 2400文字/セグメント
  const charLimitPerSegment = BASE_CHAR_LIMIT;  // 2400文字固定

  console.log(`  📊 Total segments: ${totalSegments}, ${charLimitPerSegment} chars/segment (4x600 chunks each)`);

  const segments: ChunkSegment[] = [];
  for (let i = 0; i < totalSegments; i++) {
    const startTime = i * stepSeconds;
    const endTime = Math.min((i + 1) * stepSeconds, durationSeconds);

    segments.push({
      index: i,
      startTime,
      endTime,
      charLimit: charLimitPerSegment,
      isFirstChunk: i === 0,
      type: 'mechanical',
    });
  }

  return segments;
}

/**
 * TwitterのメディアURLとメタデータを取得（VxTwitter API経由）
 */
async function getTwitterMediaAndMetadata(tweetId: string): Promise<{
  media: { type: string; url: string }[];
  username: string;
  text: string;
}> {
  try {
    const response = await axios.get(`https://api.vxtwitter.com/Twitter/status/${tweetId}`, {
      timeout: 10000,
    });

    const tweet = response.data;
    const media: { type: string; url: string }[] = [];

    if (tweet.media_extended) {
      for (const item of tweet.media_extended) {
        if (item.type === 'image') {
          media.push({ type: 'image', url: item.url });
        } else if (item.type === 'video' || item.type === 'gif') {
          const videoUrl = item.url;
          if (videoUrl) {
            media.push({ type: 'video', url: videoUrl });
          }
        }
      }
    }

    const username = tweet.user_screen_name || '';
    const text = tweet.text || '';

    return { media, username, text };
  } catch (error: any) {
    console.error(`❌ Twitter media fetch error for ${tweetId}:`, error.message);
    return { media: [], username: '', text: '' };
  }
}

/**
 * YouTube字幕を取得
 */
async function getYouTubeTranscript(videoId: string): Promise<{ text: string; offset: number; duration: number }[]> {
  try {
    const { YoutubeTranscript } = await import('youtube-transcript');
    const transcript = await YoutubeTranscript.fetchTranscript(videoId);
    return transcript.map((item: any) => ({
      text: item.text,
      offset: item.offset,
      duration: item.duration,
    }));
  } catch (error: any) {
    console.error(`❌ YouTube transcript fetch error:`, error.message);
    return [];
  }
}

/**
 * YouTube動画をダウンロード（メタデータ付き）
 */
async function downloadYouTubeVideo(videoId: string): Promise<{ path: string | null; duration: number; title: string }> {
  const tempDir = path.join(__dirname, '..', 'temp');
  const videoPath = path.join(tempDir, `${videoId}.mp4`);

  try {
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    console.log('    Downloading YouTube video...');
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;

    const info = await ytdl.getInfo(videoUrl);
    const duration = parseInt(info.videoDetails.lengthSeconds);
    const title = info.videoDetails.title;

    console.log(`    Video: ${title}`);
    console.log(`    Duration: ${duration}s (${Math.floor(duration / 60)}min)`);

    // フォーマット選択（最小サイズ優先）
    let format;
    const formats = info.formats.filter(f => f.hasVideo && f.hasAudio);

    if (formats.length > 0) {
      // 最小解像度を選択
      format = formats.sort((a, b) => {
        const aHeight = parseInt(a.qualityLabel || '0');
        const bHeight = parseInt(b.qualityLabel || '0');
        return aHeight - bHeight;
      })[0];
    } else {
      // 動画のみまたは音声のみ
      format = info.formats.filter(f => f.hasVideo || f.hasAudio)[0];
    }

    if (!format) {
      throw new Error('No suitable format found');
    }

    console.log(`    Selected format: ${format.qualityLabel || 'audio only'}, Container: ${format.container}`);

    // ダウンロード
    const video = ytdl(videoUrl, { format });
    const writeStream = fs.createWriteStream(videoPath);

    return new Promise((resolve, reject) => {
      let downloadedBytes = 0;

      video.pipe(writeStream);

      video.on('progress', (chunkLength, downloaded, total) => {
        downloadedBytes = downloaded;
        const percent = ((downloaded / total) * 100).toFixed(1);
        process.stdout.write(`\r    Download progress: ${percent}%`);
      });

      writeStream.on('finish', () => {
        console.log('\n    ✅ Download complete');
        const stats = fs.statSync(videoPath);
        console.log(`    File size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
        resolve({ path: videoPath, duration, title });
      });

      video.on('error', (error) => {
        console.error('\n    ❌ Download error:', error.message);
        resolve({ path: null, duration, title });
      });

      writeStream.on('error', (error) => {
        console.error('\n    ❌ Write error:', error.message);
        resolve({ path: null, duration, title });
      });
    });
  } catch (error: any) {
    console.error('❌ YouTube download error:', error.message);

    // メタデータのみ取得を試みる
    try {
      const info = await ytdl.getInfo(`https://www.youtube.com/watch?v=${videoId}`);
      return {
        path: null,
        duration: parseInt(info.videoDetails.lengthSeconds),
        title: info.videoDetails.title
      };
    } catch {
      return { path: null, duration: 0, title: 'Unknown' };
    }
  }
}

/**
 * YouTubeサムネイルをダウンロード（フォールバック）
 */
async function downloadYouTubeThumbnail(videoId: string): Promise<string | null> {
  const tempDir = path.join(__dirname, '..', 'temp');
  const thumbPath = path.join(tempDir, `${videoId}_thumb.jpg`);

  const urls = [
    `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
    `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
    `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`
  ];

  for (const url of urls) {
    try {
      const response = await axios.get(url, { responseType: 'arraybuffer', timeout: 10000 });
      if (response.status === 200) {
        fs.writeFileSync(thumbPath, response.data);
        console.log(`    ✅ Thumbnail downloaded: ${url.split('/').pop()}`);
        return thumbPath;
      }
    } catch {
      continue;
    }
  }

  console.error('    ❌ Failed to download thumbnail');
  return null;
}

/**
 * Gemini File APIで動画をアップロード
 */
/**
 * Gemini File APIにファイルをアップロード
 */
async function uploadToGeminiFileAPI(filePath: string, mimeType: string): Promise<any> {
  try {
    console.log('    Uploading to Gemini File API...');
    const uploadResult = await fileManager.uploadFile(filePath, {
      mimeType,
      displayName: path.basename(filePath),
    });

    console.log(`    ✅ Uploaded: ${uploadResult.file.uri}`);

    // 動画の場合は処理完了を待機
    if (mimeType.startsWith('video/')) {
      let file = await fileManager.getFile(uploadResult.file.name);

      while (file.state === 'PROCESSING') {
        process.stdout.write('.');
        await new Promise(resolve => setTimeout(resolve, 5000));
        file = await fileManager.getFile(uploadResult.file.name);
      }

      console.log('\n    ✅ Processing complete');

      if (file.state === 'FAILED') {
        throw new Error('File processing failed on Gemini API');
      }
    }

    return uploadResult.file;
  } catch (error: any) {
    console.error('❌ Gemini File API upload error:', error.message);
    throw error;
  }
}

/**
 * Gemini 2.5で画像を解析（REST API）
 */
async function analyzeImageWithGemini(imageUrl: string): Promise<{ title: string; content: string }> {
  try {
    const response = await axios.get(imageUrl, {
      responseType: 'arraybuffer',
      timeout: 30000,
    });

    const imageData = Buffer.from(response.data).toString('base64');
    const mimeType = response.headers['content-type'] || 'image/jpeg';

    const apiUrl = `https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key=${process.env.GEMINI_API_KEY}`;

    const result = await axios.post(
      apiUrl,
      {
        contents: [
          {
            parts: [
              {
                inline_data: {
                  mime_type: mimeType,
                  data: imageData,
                },
              },
              {
                text: `Analyze this image for Live2D/VTuber technical content. Provide output in the following JSON format:

{
  "title": "A concise 10-15 word description",
  "content": "Comprehensive analysis covering: character modeling techniques (parts separation, layer structure), rigging methods, physics simulation elements visible, visual effects (shading, lighting techniques), animation principles demonstrated, artistic style and mood, software/tools identifiable, any context or purpose that helps understand the content. Keep under 2400 characters in English."
}

CRITICAL PRIVACY REQUIREMENTS:
- Do NOT include usernames, account names, display names, or any personal identifiers
- Do NOT mention specific creator/channel names
- You MAY include opinions, feelings, artistic impressions, and context to aid understanding
- You MAY describe the mood, theme, and subjective qualities
- Replace any visible usernames with generic terms like "the creator", "the artist", "this work"

Provide ONLY the JSON, no other text.`,
              },
            ],
          },
        ],
      },
      { timeout: 60000 }
    );

    const responseText = result.data.candidates[0]?.content?.parts[0]?.text || '';

    // JSONをパース
    try {
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return {
          title: parsed.title || 'Image content',
          content: parsed.content || responseText,
        };
      }
    } catch (parseError) {
      console.warn('  ⚠️  Failed to parse JSON, using raw text');
    }

    // JSONパース失敗時はcontentのみ
    return { title: 'Image content', content: responseText };
  } catch (error: any) {
    console.error('❌ Gemini image analysis error:', error.response?.data || error.message);
    return { title: '', content: '' };
  }
}

/**
 * GeminiでYouTube動画を解析（URL直接送信）
 */
/**
 * YouTube動画のメタデータ取得（タイトル、長さ、チャンネル名、チャプター）
 */
async function getYouTubeMetadata(videoId: string): Promise<{
  title: string;
  duration: number;
  channelName: string;
  chapters: { time: string; title: string }[];
}> {
  try {
    const response = await axios.get(
      `https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id=${videoId}&key=${process.env.YOUTUBE_API_KEY}`
    );

    if (response.data.items && response.data.items.length > 0) {
      const video = response.data.items[0];
      const title = video.snippet.title;
      const channelName = video.snippet.channelTitle || '';

      // ISO 8601 duration (PT1H2M10S) を秒に変換
      const durationStr = video.contentDetails.duration;
      const match = durationStr.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
      const hours = parseInt(match?.[1] || '0');
      const minutes = parseInt(match?.[2] || '0');
      const seconds = parseInt(match?.[3] || '0');
      const duration = hours * 3600 + minutes * 60 + seconds;

      // チャプター情報は説明文から抽出（簡易実装）
      const description = video.snippet.description || '';
      const chapters = extractChaptersFromDescription(description);

      return { title, duration, channelName, chapters };
    }

    return { title: '', duration: 0, channelName: '', chapters: [] };
  } catch (error: any) {
    console.error('  ⚠️  Failed to get YouTube metadata:', error.message);
    return { title: '', duration: 0, channelName: '', chapters: [] };
  }
}

/**
 * YouTube説明文からチャプター情報を抽出
 */
function extractChaptersFromDescription(description: string): { time: string; title: string }[] {
  const chapters: { time: string; title: string }[] = [];
  const lines = description.split('\n');

  for (const line of lines) {
    // 00:00 Chapter Title 形式を検索
    const match = line.match(/^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$/);
    if (match) {
      chapters.push({
        time: match[1],
        title: match[2].trim(),
      });
    }
  }

  return chapters;
}

/**
 * 時間（秒）をMM:SS形式に変換
 */
function secondsToTimeString(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 字幕を時間範囲でフィルター
 */
function filterTranscriptByTimeRange(
  transcript: { text: string; offset: number }[],
  startSeconds: number,
  endSeconds: number
): { text: string; offset: number }[] {
  return transcript.filter(t => {
    const tSeconds = t.offset / 1000;
    return tSeconds >= startSeconds && tSeconds < endSeconds;
  });
}

/**
 * YouTubeセグメントを解析（機械的時間ベース分割のみ）
 * 1回のAPI呼び出しで4つの600文字チャンクを配列で取得
 */
async function analyzeYouTubeSegment(
  videoId: string,
  videoTitle: string,
  segment: ChunkSegment,
  transcript: { text: string; offset: number }[]
): Promise<{ chunks: string[]; title?: string }> {
  try {
    const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });

    // セグメントの字幕を抽出
    const segmentTranscript = filterTranscriptByTimeRange(transcript, segment.startTime, segment.endTime);

    let transcriptText = '';
    if (segmentTranscript.length > 0) {
      const maxLines = 80;
      transcriptText = '\n\nTranscript for this segment:\n' + segmentTranscript.slice(0, maxLines).map(t =>
        `[${formatTime(t.offset)}] ${t.text}`
      ).join('\n');
      if (segmentTranscript.length > maxLines) {
        transcriptText += '\n... (truncated)';
      }
    }

    const timeRange = `${secondsToTimeString(segment.startTime)} - ${secondsToTimeString(segment.endTime)}`;

    // 機械的分割: 時間範囲のみで解析
    const prompt = `Analyze the time segment ${timeRange} of this video for Live2D/VTuber content.${transcriptText ? ' The transcript is provided below.' : ''}
${transcriptText}

Return a JSON object with the following structure:
${segment.isFirstChunk ? `{
  "title": "A concise 10-15 word description of the entire video",
  "chunks": [
    {"content": "First 600-char comprehensive analysis"},
    {"content": "Second 600-char comprehensive analysis"},
    {"content": "Third 600-char comprehensive analysis"},
    {"content": "Fourth 600-char comprehensive analysis"}
  ]
}` : `{
  "chunks": [
    {"content": "First 600-char comprehensive analysis"},
    {"content": "Second 600-char comprehensive analysis"},
    {"content": "Third 600-char comprehensive analysis"},
    {"content": "Fourth 600-char comprehensive analysis"}
  ]
}`}

Each chunk should cover:
- Character rigging and animation techniques demonstrated
- Physics simulation (hair, clothing, accessories movement)
- Facial expression mapping and lip-sync methods
- Layer deformation and mesh transformation
- Visual effects (shading, lighting, post-processing)
- Artistic style and mood
- Software/tools identifiable
- Context or purpose that helps understand the content
- Include timestamps as **Description (MM:SS)** for key moments

CRITICAL PRIVACY REQUIREMENTS:
- Do NOT include channel names, usernames, display names, or any personal identifiers
- Do NOT mention specific creator names
- You MAY include opinions, feelings, artistic impressions, and context to aid understanding
- You MAY describe the mood, theme, and subjective qualities
- Replace any visible usernames with generic terms like "the creator", "the artist", "this work"
- Each chunk MUST be exactly around 600 characters
- Total of 4 chunks = ~2400 characters
- Write in English
- Provide ONLY the JSON, no other text`;

    const result = await model.generateContent([
      { text: youtubeUrl },
      { text: prompt },
    ]);

    const responseText = result.response.text();

    // JSONをパース
    try {
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);

        const chunks = parsed.chunks?.map((c: any) => c.content) || [];
        const title = parsed.title;

        if (chunks.length > 0) {
          console.log(`    ✅ Received ${chunks.length} chunks from API`);
          return { chunks, title };
        }
      }
    } catch (parseError) {
      console.warn('    ⚠️  Failed to parse JSON response, falling back to text splitting');
    }

    // JSONパース失敗時のフォールバック
    return { chunks: [responseText] };

  } catch (error: any) {
    console.error(`    ❌ Segment analysis error:`, error.message);
    return { chunks: [] };
  }
}

async function analyzeYouTubeVideoWithGemini(
  videoId: string,
  videoTitle: string,
  duration: number,
  transcript?: { text: string; offset: number }[]
): Promise<{ description: string; timestamps: Timestamp[]; videoTitle: string; duration: number }> {
  try {
    const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
    console.log(`    Analyzing YouTube video via URL: ${youtubeUrl}`);
    console.log(`    Title: ${videoTitle}, Duration: ${duration}s (${Math.floor(duration / 60)}min)`);

    // 3分(180秒)以下の短い動画：通常処理
    if (duration <= 180) {
      console.log(`    📹 Short video mode (≤3 min)`);
      const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });

      let transcriptText = '';
      if (transcript && transcript.length > 0) {
        transcriptText = '\n\nVideo transcript:\n' + transcript.slice(0, 50).map(t =>
          `[${formatTime(t.offset)}] ${t.text}`
        ).join('\n');
        if (transcript.length > 50) {
          transcriptText += '\n... (truncated)';
        }
      }

      const prompt = `Analyze this video for Live2D/VTuber content.${transcriptText ? ' The transcript is provided below.' : ''}
${transcriptText}

Provide comprehensive analysis covering:
- Character rigging and animation techniques demonstrated
- Physics simulation (hair, clothing, accessories movement)
- Facial expression mapping and lip-sync methods
- Layer deformation and mesh transformation
- Visual effects (shading, lighting, post-processing)
- Artistic style and mood
- Software/tools identifiable from the content
- Context or purpose that helps understand the content
- Important moments: 3-5 timestamps formatted as **Description (MM:SS)**

CRITICAL PRIVACY REQUIREMENTS:
- Do NOT include channel names, usernames, display names, or any personal identifiers
- Do NOT mention specific creator names
- You MAY include opinions, feelings, artistic impressions, and context to aid understanding
- You MAY describe the mood, theme, and subjective qualities
- Replace any visible usernames with generic terms like "the creator", "the artist", "this work"
- Skip sections that don't apply
- Keep the total response under 2400 characters
- Write in English`;

      const result = await model.generateContent([
        { text: youtubeUrl },
        { text: prompt },
      ]);

      const responseText = result.response.text();
      const timestamps = extractTimestamps(responseText);

      return { description: responseText, timestamps, videoTitle, duration };
    }

    // 3分超の長い動画：機械的分割のみ
    console.log(`    📹 Long video mode (>3 min) - using mechanical segmentation`);

    const segments = calculateMechanicalSegments(duration);

    if (segments.length === 0) {
      throw new Error('No segments generated for long video');
    }

    console.log(`    🎬 Processing ${segments.length} segments...`);

    const allChunks: string[] = [];
    const allTimestamps: Timestamp[] = [];
    let videoTitleExtracted: string | undefined;

    for (const segment of segments) {
      console.log(`    📍 Analyzing Segment ${segment.index + 1}/${segments.length} (${secondsToTimeString(segment.startTime)} - ${secondsToTimeString(segment.endTime)})`);

      const { chunks, title } = await analyzeYouTubeSegment(
        videoId,
        videoTitle,
        segment,
        transcript || []
      );

      // 最初のセグメントからタイトルを保存
      if (segment.isFirstChunk && title) {
        videoTitleExtracted = title;
        console.log(`    📝 Extracted video title: "${videoTitleExtracted}"`);
      }

      if (chunks && chunks.length > 0) {
        // 4つのチャンクをそのまま追加（APIが既に600文字で分割済み）
        allChunks.push(...chunks);

        // 各チャンクからタイムスタンプを抽出
        for (const chunk of chunks) {
          const timestamps = extractTimestamps(chunk);
          allTimestamps.push(...timestamps);
        }

        console.log(`    ✅ Added ${chunks.length} chunks (avg ${Math.round(chunks.reduce((sum, c) => sum + c.length, 0) / chunks.length)} chars each)`);
      }

      // API制限対策（セグメント間で3秒待機）
      await new Promise(resolve => setTimeout(resolve, 3000));
    }

    // 全チャンクの結合は不要（既に600文字単位で分割済み）
    console.log(`    ✅ Total ${allChunks.length} chunks generated from ${segments.length} segments`);

    // チャンクをセパレータで結合（saveMediaChunksで再分割される）
    const combinedDescription = allChunks.join('\n\n');

    return {
      description: combinedDescription,
      timestamps: allTimestamps,
      videoTitle,
      duration
    };

  } catch (error: any) {
    console.error('❌ Gemini YouTube URL analysis error:', error.message);
    return { description: '', timestamps: [], videoTitle, duration };
  }
}

/**
 * Geminiで動画を解析（動画ファイル直接 + 字幕、File API使用）
 */
async function analyzeVideoWithGemini(
  videoPath: string,
  duration: number,
  transcript?: { text: string; offset: number }[]
): Promise<{ title: string; description: string; timestamps: Timestamp[] }> {
  let uploadedFile: any = null;

  try {
    // モデル選択: 10分以上ならPro、それ以外はFlash（レート制限回避のため2.0使用）
    const modelName = duration > 600 ? 'gemini-2.5-pro' : 'gemini-2.0-flash';
    console.log(`    Selected model: ${modelName} (duration: ${duration}s)`);

    const model = genAI.getGenerativeModel({ model: modelName });

    // File APIにアップロード
    uploadedFile = await uploadToGeminiFileAPI(videoPath, 'video/mp4');

    // 字幕情報を含めたプロンプト
    let transcriptText = '';
    if (transcript && transcript.length > 0) {
      transcriptText = '\n\nVideo transcript:\n' + transcript.slice(0, 50).map(t =>
        `[${formatTime(t.offset)}] ${t.text}`
      ).join('\n');
      if (transcript.length > 50) {
        transcriptText += '\n... (truncated)';
      }
    }

    const prompt = `Analyze this video for Live2D/VTuber content. Provide output in the following JSON format:

{
  "title": "A concise 10-15 word description",
  "content": "Comprehensive analysis covering: character rigging and animation techniques, physics simulation (hair, clothing movement), facial expression mapping, layer deformation methods, visual effects implementation, artistic style and mood, software/tools used, context or purpose of the content. Include 3-5 timestamps as **Description (MM:SS)**. Keep under 2400 characters in English."
}

${transcriptText ? 'Transcript:\n' + transcriptText : ''}

CRITICAL PRIVACY REQUIREMENTS:
- Do NOT include usernames, account names, display names, or any personal identifiers
- Do NOT mention specific creator/channel names
- You MAY include opinions, feelings, artistic impressions, and context to aid understanding
- You MAY describe the mood, theme, and subjective qualities
- Replace any visible usernames with generic terms like "the creator", "the artist", "this work"

Provide ONLY the JSON, no other text.`;

    const result = await model.generateContent([
      {
        fileData: {
          mimeType: uploadedFile.mimeType,
          fileUri: uploadedFile.uri,
        },
      },
      { text: prompt },
    ]);

    const responseText = result.response.text();

    // JSONをパース
    try {
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        const timestamps = extractTimestamps(parsed.content || '');
        return {
          title: parsed.title || 'Video content',
          description: parsed.content || responseText,
          timestamps,
        };
      }
    } catch (parseError) {
      console.warn('  ⚠️  Failed to parse JSON, using raw text');
    }

    // JSONパース失敗時
    const timestamps = extractTimestamps(responseText);
    return { title: 'Video content', description: responseText, timestamps };
  } catch (error: any) {
    console.error('❌ Gemini video analysis error:', error.message);
    return { title: '', description: '', timestamps: [] };
  } finally {
    // File APIからファイルを削除
    if (uploadedFile) {
      try {
        await fileManager.deleteFile(uploadedFile.name);
        console.log('    🗑️  Deleted from Gemini File API');
      } catch (e: any) {
        console.error('    ⚠️  Failed to delete file:', e.message);
      }
    }
  }
}

/**
 * サムネイル画像から動画内容を推測（フォールバック）
 */
async function analyzeVideoFromThumbnail(
  thumbnailPath: string,
  title: string,
  transcript?: { text: string; offset: number }[]
): Promise<{ description: string; timestamps: Timestamp[] }> {
  try {
    console.log('    Analyzing from thumbnail (fallback mode)...');

    const imageData = fs.readFileSync(thumbnailPath).toString('base64');
    const apiUrl = `https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key=${process.env.GEMINI_API_KEY}`;

    let transcriptText = '';
    if (transcript && transcript.length > 0) {
      transcriptText = '\n\nAvailable transcript:\n' + transcript.slice(0, 30).map(t =>
        `[${formatTime(t.offset)}] ${t.text}`
      ).join('\n');
    }

    const result = await axios.post(
      apiUrl,
      {
        contents: [
          {
            parts: [
              {
                inline_data: {
                  mime_type: 'image/jpeg',
                  data: imageData,
                },
              },
              {
                text: `This video is currently access-restricted or deleted. Based on the thumbnail image and title, infer what the video content might have been about.

**Video Title**: ${title}
${transcriptText}

Provide:
1. A 300-character analysis of what this video likely contained (in English)
2. If transcript is available, extract 3-5 key timestamps

Format: [MM:SS] Description`,
              },
            ],
          },
        ],
      },
      { timeout: 60000 }
    );

    const responseText = result.data.candidates[0]?.content?.parts[0]?.text || '';
    const timestamps = extractTimestamps(responseText);
    const description = responseText.replace(/\[\d{1,2}:\d{2}\].*$/gm, '').trim();

    return { description, timestamps };
  } catch (error: any) {
    console.error('❌ Thumbnail analysis error:', error.message);
    return { description: '', timestamps: [] };
  }
}

/**
 * ダウンロードしたファイルを削除
 */
function cleanupFile(filePath: string) {
  try {
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      console.log(`    🗑️  Cleaned up: ${path.basename(filePath)}`);
    }
  } catch (error: any) {
    console.error(`    ⚠️  Cleanup failed: ${error.message}`);
  }
}

/**
 * 時間をフォーマット（ミリ秒 → MM:SS）
 */
function formatTime(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * レスポンスからタイムスタンプを抽出
 * 対応形式:
 * 1. **説明 (MM:SS)** または **説明 (MM:SS - MM:SS)**
 * 2. [MM:SS] 説明
 */
function extractTimestamps(text: string): Timestamp[] {
  const timestamps: Timestamp[] = [];

  // 新形式: **説明 (MM:SS)** または **説明 (MM:SS - MM:SS)**
  const newFormatRegex = /\*\*(.+?)\s*\((\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\)\*\*/g;
  let match;
  while ((match = newFormatRegex.exec(text)) !== null) {
    timestamps.push({
      time: match[2].trim(),
      description: match[1].trim(),
    });
  }

  // 旧形式: [MM:SS] 説明
  const oldFormatRegex = /\[(\d{1,2}:\d{2})\]\s*(.+?)(?=\[|$)/g;
  while ((match = oldFormatRegex.exec(text)) !== null) {
    timestamps.push({
      time: match[1],
      description: match[2].trim(),
    });
  }

  return timestamps;
}

/**
 * テキストからタイムスタンプ表記を削除
 */
function removeTimestampsFromText(text: string): string {
  // **説明 (MM:SS)** または **説明 (MM:SS - MM:SS)** を削除
  let cleanText = text.replace(/\*\*(.+?)\s*\((\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\)\*\*/g, '');

  // [MM:SS] 説明 を削除
  cleanText = cleanText.replace(/\[(\d{1,2}:\d{2})\]\s*(.+?)(?=\[|$)/g, '');

  // 連続する空行を1つに
  cleanText = cleanText.replace(/\n\n+/g, '\n\n');

  return cleanText.trim();
}

/**
 * 600文字ごとに意味のつながりで分割（オーバーラップ50-100文字）
 */
function splitIntoChunksWithOverlap(text: string, maxLength: number = 600, overlapLength: number = 75): string[] {
  if (text.length <= maxLength) {
    return [text];
  }

  const chunks: string[] = [];
  let currentPos = 0;

  while (currentPos < text.length) {
    let endPos = currentPos + maxLength;

    if (endPos >= text.length) {
      chunks.push(text.slice(currentPos).trim());
      break;
    }

    const searchText = text.slice(currentPos, endPos);
    const breakChars = ['.', '!', '?', '\n'];

    // 文の終わりを探す
    let breakPos = -1;
    for (let i = searchText.length - 1; i >= Math.max(0, searchText.length - 100); i--) {
      if (breakChars.includes(searchText[i])) {
        breakPos = currentPos + i + 1;
        break;
      }
    }

    // 見つからなければカンマや空白で分割
    if (breakPos === -1) {
      const punctuation = [',', ';', ' '];
      for (let i = searchText.length - 1; i >= Math.max(0, searchText.length - 100); i--) {
        if (punctuation.includes(searchText[i])) {
          breakPos = currentPos + i + 1;
          break;
        }
      }
    }

    if (breakPos === -1) {
      breakPos = endPos;
    }

    const chunk = text.slice(currentPos, breakPos).trim();
    if (chunk) chunks.push(chunk);

    // オーバーラップ: 前のチャンクの最後の1-2文を次のチャンクの先頭に含める
    // 次の開始位置を戻す（約50-100文字分）
    let overlapStart = breakPos;
    let sentenceCount = 0;

    // 最後の1-2文を見つける
    for (let i = breakPos - 1; i >= currentPos && sentenceCount < 2; i--) {
      if (breakChars.includes(text[i])) {
        sentenceCount++;
        if (sentenceCount === 1 || sentenceCount === 2) {
          overlapStart = i + 1;
        }
      }
      // 約100文字以上遡ったら終了
      if (breakPos - i > 100) break;
    }

    // オーバーラップが50-100文字の範囲内であることを確認
    const overlapSize = breakPos - overlapStart;
    if (overlapSize >= 50 && overlapSize <= 100) {
      currentPos = overlapStart;
    } else if (overlapSize > 100) {
      // 100文字を超える場合は100文字に制限
      currentPos = breakPos - 100;
    } else {
      // 50文字未満の場合はオーバーラップなし
      currentPos = breakPos;
    }
  }

  return chunks.filter(c => c.length > 0);
}

// GDPR対応: 個人情報を含むメタデータ注入関数を削除
// チャンクにはGeminiが生成した技術的な内容のみを保存

/**
 * 既存のタグを取得
 */
async function getExistingTags(connection: mysql.Connection): Promise<string[]> {
  const [tags]: any = await connection.query('SELECT DISTINCT name FROM tags');
  return tags.map((t: any) => t.name);
}

/**
 * 全チャンクからAIメタデータを生成（summary, ai_tags, ai_title, user_intent）
 */
async function generateAIMetadata(
  allChunksText: string[],
  existingTags: string[],
  mediaType: string
): Promise<{ summary: string; ai_tags: string[]; ai_title: string; user_intent: string[] }> {
  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });

    // 全チャンクを結合（最大8000文字に制限）
    const combinedText = allChunksText.join('\n\n').substring(0, 8000);

    const existingTagsStr = existingTags.length > 0
      ? `\n\nExisting tags in database (use relevant ones): ${existingTags.join(', ')}`
      : '';

    const prompt = `Based on the following Live2D/VTuber content analysis, generate metadata in JSON format:

CONTENT:
${combinedText}
${existingTagsStr}

Return a JSON object with the following structure:
{
  "ai_title": "A concise 10-15 word descriptive title in English",
  "summary": "A comprehensive 300-character summary in English covering the main technical points, artistic style, and context",
  "ai_tags": ["tag1", "tag2", "tag3", ...],
  "user_intent": [
    "Question 1 that this content answers",
    "Question 2 that this content answers",
    "Question 3 that this content answers"
  ]
}

REQUIREMENTS FOR ai_tags:
- Maximum 10 tags
- Prioritize using existing tags from the database when relevant
- Add new technical terms that capture key points
- Focus on: techniques, tools, features, styles, purposes
- Use lowercase, underscore_separated format (e.g., "physics_simulation", "facial_rigging")
- Examples: "live2d", "character_rigging", "physics_simulation", "tutorial", "cubism", "vtube_studio"

REQUIREMENTS FOR user_intent:
- Generate exactly 3 questions that this content helps answer
- Questions should reflect what Live2D creators, VTuber creators, or VTuber enthusiasts would search for
- Focus on practical problems, how-to questions, and technical inquiries
- Write questions in natural English (as users would type them)
- Examples:
  * "How do I set up physics simulation for hair in Live2D?"
  * "What are the best rigging techniques for facial expressions?"
  * "How can I improve lip sync accuracy in my VTuber model?"
  * "What software do I need to create a Live2D character?"
  * "How do I troubleshoot physics parameters that look unnatural?"

CRITICAL PRIVACY REQUIREMENTS:
- Do NOT include usernames, channel names, creator names, or any personal identifiers
- Do NOT mention specific individuals
- Focus on technical content, artistic qualities, and educational value
- Write objectively as if documenting a technical resource
- All output must be in English

Provide ONLY the JSON, no other text.`;

    const result = await model.generateContent(prompt);
    const responseText = result.response.text();

    // JSONをパース
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);

      return {
        ai_title: parsed.ai_title || '',
        summary: parsed.summary || '',
        ai_tags: (parsed.ai_tags || []).slice(0, 10), // 最大10個
        user_intent: (parsed.user_intent || []).slice(0, 3), // 正確に3個
      };
    }

    throw new Error('Failed to parse JSON response');

  } catch (error: any) {
    console.error('❌ AI metadata generation error:', error.message);
    return {
      ai_title: '',
      summary: '',
      ai_tags: [],
      user_intent: [],
    };
  }
}

/**
 * メディア解析結果をpost_chunksに保存
 */
async function saveMediaChunks(
  connection: mysql.Connection,
  postId: string,
  mediaType: string,
  analysisResults: {
    type: string;
    content: string;
    timestamps?: Timestamp[];
    videoTitle?: string;
    duration?: number;
    channelName?: string;
    chapters?: { time: string; title: string }[];
    username?: string;
    summary?: string;
  }[]
) {
  await connection.query(
    'DELETE FROM post_chunks WHERE post_id = ? AND chunk_source = ?',
    [postId, 'media_analysis']
  );

  const [maxIndex]: any = await connection.query(
    'SELECT MAX(chunk_index) as max_idx FROM post_chunks WHERE post_id = ?',
    [postId]
  );

  let chunkIndex = maxIndex[0].max_idx !== null ? maxIndex[0].max_idx + 1 : 0;

  for (const result of analysisResults) {
    if (!result.content) continue;

    // GDPR対応: 個人情報は保存しない
    // Geminiが生成した技術的な内容のみを保存

    // YouTube長編動画の場合は既に600文字チャンクで分割済み（\n\nで区切られている）
    // それ以外はオーバーラップ付きで600文字に分割
    let chunks: string[];
    if (mediaType === 'YouTube' && result.duration && result.duration > 180) {
      // 長編動画: 既に600文字で分割済み（APIが生成）
      chunks = result.content.split('\n\n').filter(c => c.trim().length > 0);
      console.log(`  📦 Using pre-generated chunks: ${chunks.length} chunks`);
    } else {
      // 短編動画 or Twitter: オーバーラップ付きで分割
      chunks = splitIntoChunksWithOverlap(result.content, 600);
      console.log(`  ✂️  Split with overlap: ${chunks.length} chunks`);
    }

    // 全てのタイムスタンプを抽出（結果全体から）
    const allTimestamps = result.timestamps || [];

    for (let i = 0; i < chunks.length; i++) {
      // GDPR対応: 個人情報を含む文脈メタデータは注入しない
      // チャンクにはGeminiが生成した技術的な内容のみを保存
      let chunkText = chunks[i];

      // このチャンクに含まれるタイムスタンプを抽出
      const chunkTimestamps = extractTimestamps(chunkText);

      // チャンクテキストからタイムスタンプ表記を削除
      chunkText = removeTimestampsFromText(chunkText);

      const chunkId = uuid.v7();
      const metadata: any = {
        media: mediaType,
        source: 'media_analysis',
        type: `${mediaType.toLowerCase()}_${result.type}`,
      };

      // タイムスタンプが存在する場合、metadataに追加
      if (chunkTimestamps.length > 0) {
        metadata.timestamps = chunkTimestamps.map(t => ({
          time: t.time,
          topic: t.description,
        }));
      }

      await connection.query(
        `INSERT INTO post_chunks
         (id, post_id, chunk_index, chunk_text, embedding, metadata, chunk_media, chunk_source, chunk_type)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          chunkId,
          postId,
          chunkIndex++,
          chunkText,
          null,
          JSON.stringify(metadata),
          mediaType,
          'media_analysis',
          `${mediaType.toLowerCase()}_${result.type}`,
        ]
      );

      console.log(`  ✅ Saved ${result.type} chunk (${chunkText.length} chars, ${chunkTimestamps.length} timestamps) - GDPR compliant`);
    }

  }
}

/**
 * メイン処理
 */
async function analyzeMediaWithGemini() {
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT) || 4000,
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB || 's13_l2t',
  });

  try {
    console.log('=== Media Analysis (Gemini 2.0 Flash) ===\n');
    console.log('Features:');
    console.log('  - Twitter: Image + Video analysis (direct file)');
    console.log('  - YouTube: Video analysis with URL direct method');
    console.log('  - Mechanical segmentation for long videos');
    console.log('  - AI metadata generation (summary, ai_tags, ai_title)');
    console.log('  - GDPR compliant (no personal identifiers)');
    console.log('  - Output language: English\n');

    // 既存のタグを取得
    console.log('📥 Fetching existing tags from database...');
    const existingTags = await getExistingTags(connection);
    console.log(`  ✅ Found ${existingTags.length} existing tags\n`);

    const [twitterPosts]: any = await connection.query(
      'SELECT id, source, type, identifier, metadata FROM posts WHERE type = ? LIMIT 1',
      ['twitter']
    );

    const [youtubePosts]: any = await connection.query(
      'SELECT id, source, type, identifier, metadata FROM posts WHERE type = ? LIMIT 2',
      ['YouTube']
    );

    const posts: Post[] = [...twitterPosts, ...youtubePosts];
    console.log(`Target posts: ${posts.length}\n`);

    for (const post of posts) {
      console.log(`\n[Processing] ${post.source}`);
      console.log(`  Type: ${post.type}`);

      const analysisResults: { type: string; content: string; timestamps?: Timestamp[] }[] = [];

      if (post.type === 'twitter') {
        console.log('  📥 Fetching Twitter media and metadata...');
        const { media, username, text } = await getTwitterMediaAndMetadata(post.identifier);
        console.log(`  Found ${media.length} media items from @${username}`);

        for (const item of media) {
          console.log(`  🔍 Analyzing ${item.type}...`);

          if (item.type === 'image') {
            const { title, content } = await analyzeImageWithGemini(item.url);
            if (content) {
              analysisResults.push({
                type: 'image',
                content,
                title, // AI生成タイトル
                username,
                summary: text, // ツイート本文
              });
            }
          } else if (item.type === 'video') {
            const response = await axios.get(item.url, {
              responseType: 'arraybuffer',
              timeout: 60000,
            });

            const tempPath = path.join(__dirname, '..', 'temp', `twitter_${post.identifier}.mp4`);
            fs.writeFileSync(tempPath, response.data);

            const stats = fs.statSync(tempPath);
            console.log(`    Video size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);

            const { title, description, timestamps } = await analyzeVideoWithGemini(tempPath, 30); // Twitter動画は通常短い
            cleanupFile(tempPath);

            if (description) {
              analysisResults.push({
                type: 'video',
                content: description,
                title, // AI生成タイトル
                timestamps,
                username,
                summary: text, // ツイート本文
              });
            }
          }

          await new Promise(resolve => setTimeout(resolve, 3000));
        }

        if (analysisResults.length > 0) {
          await saveMediaChunks(connection, post.id, 'Twitter', analysisResults);

          // AIメタデータを生成
          console.log('  🤖 Generating AI metadata (summary, ai_tags, ai_title)...');
          const allChunksText = analysisResults.map(r => r.content);
          const aiMetadata = await generateAIMetadata(allChunksText, existingTags, 'Twitter');

          if (aiMetadata.ai_title || aiMetadata.summary || aiMetadata.ai_tags.length > 0) {
            console.log(`    ✅ Generated: title="${aiMetadata.ai_title}", ${aiMetadata.ai_tags.length} tags`);
            console.log(`    📝 Summary: ${aiMetadata.summary.substring(0, 100)}...`);
            console.log(`    🏷️  Tags: ${aiMetadata.ai_tags.join(', ')}`);
            console.log(`    ❓ User Intent Questions:`);
            aiMetadata.user_intent.forEach((q, i) => console.log(`       ${i + 1}. ${q}`));

            // postsテーブルを更新
            await connection.query(
              'UPDATE posts SET ai_title = ?, summary = ?, ai_tags = ?, user_intent = ? WHERE id = ?',
              [
                aiMetadata.ai_title,
                aiMetadata.summary,
                JSON.stringify(aiMetadata.ai_tags),
                JSON.stringify(aiMetadata.user_intent),
                post.id
              ]
            );
            console.log(`    💾 Updated posts table with AI metadata`);
          }
        }

      } else if (post.type === 'YouTube') {
        console.log('  📥 Fetching YouTube metadata...');
        const { title, duration, channelName, chapters } = await getYouTubeMetadata(post.identifier);
        console.log(`  📺 Channel: ${channelName}`);
        if (chapters.length > 0) {
          console.log(`  📖 Found ${chapters.length} chapters`);
        }

        console.log('  📥 Fetching YouTube transcript...');
        const transcript = await getYouTubeTranscript(post.identifier);

        if (transcript.length > 0) {
          console.log(`  ✅ Transcript found: ${transcript.length} segments`);
        } else {
          console.log('  ⚠️  No transcript available');
        }

        console.log('  🔍 Analyzing video via YouTube URL...');

        // YouTube URLを直接Geminiに送信（機械的分割のみ）
        const { description, timestamps, videoTitle, duration: videoDuration } = await analyzeYouTubeVideoWithGemini(
          post.identifier,
          title,
          duration,
          transcript
        );

        if (description) {
          analysisResults.push({
            type: 'video',
            content: description,
            timestamps,
            videoTitle,
            duration: videoDuration,
            channelName,
            chapters,
          });
          await saveMediaChunks(connection, post.id, 'YouTube', analysisResults);

          // AIメタデータを生成
          console.log('  🤖 Generating AI metadata (summary, ai_tags, ai_title)...');
          const allChunksText = analysisResults.map(r => r.content);
          const aiMetadata = await generateAIMetadata(allChunksText, existingTags, 'YouTube');

          if (aiMetadata.ai_title || aiMetadata.summary || aiMetadata.ai_tags.length > 0) {
            console.log(`    ✅ Generated: title="${aiMetadata.ai_title}", ${aiMetadata.ai_tags.length} tags`);
            console.log(`    📝 Summary: ${aiMetadata.summary.substring(0, 100)}...`);
            console.log(`    🏷️  Tags: ${aiMetadata.ai_tags.join(', ')}`);
            console.log(`    ❓ User Intent Questions:`);
            aiMetadata.user_intent.forEach((q, i) => console.log(`       ${i + 1}. ${q}`));

            // postsテーブルを更新
            await connection.query(
              'UPDATE posts SET ai_title = ?, summary = ?, ai_tags = ?, user_intent = ? WHERE id = ?',
              [
                aiMetadata.ai_title,
                aiMetadata.summary,
                JSON.stringify(aiMetadata.ai_tags),
                JSON.stringify(aiMetadata.user_intent),
                post.id
              ]
            );
            console.log(`    💾 Updated posts table with AI metadata`);
          }
        } else {
          console.log('  ⚠️  Analysis failed');
        }

        await new Promise(resolve => setTimeout(resolve, 3000));
      }

      console.log(`  ✅ Completed: ${analysisResults.length} media analyzed`);
    }

    console.log('\n=== Analysis Complete ===');
    console.log('\nNext steps:');
    console.log('  - Generate embeddings with Gemini Embedding API');
    console.log('  - Enable vector search for media content');

  } catch (error: any) {
    console.error('❌ Error:', error.message);
    throw error;
  } finally {
    await connection.end();
  }
}

analyzeMediaWithGemini().catch(console.error);
