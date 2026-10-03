import mysql from 'mysql2/promise';
import axios from 'axios';
import * as dotenv from 'dotenv';
import { v7 as uuidv7 } from 'uuid';
import { GoogleGenerativeAI } from '@google/generative-ai';

dotenv.config();

// Gemini API初期化
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');
const embeddingModel = genAI.getGenerativeModel({ model: 'gemini-embedding-001' });

// URLからメディアタイプを判別
function detectMediaType(url: string): 'Twitter' | 'YouTube' | 'Unknown' {
  if (url.includes('twitter.com') || url.includes('x.com')) {
    return 'Twitter';
  } else if (url.includes('youtube.com') || url.includes('youtu.be')) {
    return 'YouTube';
  }
  return 'Unknown';
}

// YouTube video IDを抽出
function extractYouTubeVideoId(url: string): string | null {
  const match = url.match(/(?:embed\/|v=|watch\?v=|youtu\.be\/)([\w-]{11})/);
  return match ? match[1] : null;
}

// Twitter tweet IDを抽出
function extractTwitterTweetId(url: string): string | null {
  const match = url.match(/status\/(\d+)/);
  return match ? match[1] : null;
}

// vxTwitterからデータ取得
async function fetchTwitterData(tweetId: string) {
  try {
    const vxUrl = `https://api.vxtwitter.com/Twitter/status/${tweetId}`;
    console.log(`  📡 vxTwitter API呼び出し: ${tweetId}`);

    const response = await axios.get(vxUrl, {
      timeout: 15000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    });

    if (response.data && response.data.text) {
      const data = response.data;
      const mediaExtended = (data as any).media_extended || [];

      const hasVideo = mediaExtended.some((m: any) => m.type === 'video');
      const hasImage = mediaExtended.some((m: any) => m.type === 'photo' || m.type === 'image');
      const hasGif = mediaExtended.some((m: any) => m.type === 'gif');

      return {
        text: data.text,
        metadata: {
          media: 'Twitter',
          twitter: {
            user_name: data.user_name,
            screen_name: data.user_screen_name,
            date: data.date,
            likes: data.likes,
            retweets: data.retweets,
            replies: data.replies,
            has_video: hasVideo,
            has_image: hasImage,
            has_gif: hasGif,
            media_count: mediaExtended.length
          }
        }
      };
    }

    return null;
  } catch (error: any) {
    // レート制限エラーをチェック
    if (error.response?.status === 429 ||
        error.message.toLowerCase().includes('too many requests') ||
        error.message.toLowerCase().includes('rate limit')) {
      console.error(`  ❌ レート制限エラー: ${error.message}`);
      throw new Error('RATE_LIMIT_EXCEEDED');
    }
    console.error(`  ❌ vxTwitterエラー: ${error.message}`);
    return null;
  }
}

// YouTube Data APIからデータ取得
async function fetchYouTubeData(videoId: string) {
  try {
    const apiKey = process.env.YOUTUBE_API_KEY;
    if (!apiKey) {
      console.error('  ❌ YOUTUBE_API_KEYが設定されていません');
      return null;
    }

    const url = `https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id=${videoId}&key=${apiKey}`;
    console.log(`  📡 YouTube API呼び出し: ${videoId}`);

    const response = await axios.get(url);

    if (!response.data.items || response.data.items.length === 0) {
      console.error('  ❌ 動画が見つかりませんでした');
      return null;
    }

    const video = response.data.items[0];
    const snippet = video.snippet;
    const contentDetails = video.contentDetails;
    const statistics = video.statistics;

    return {
      title: snippet.title,
      description: snippet.description,
      metadata: {
        media: 'YouTube',
        youtube: {
          video_id: videoId,
          channel_name: snippet.channelTitle,
          channel_id: snippet.channelId,
          published_at: snippet.publishedAt,
          duration: contentDetails.duration,
          view_count: parseInt(statistics.viewCount || '0'),
          like_count: parseInt(statistics.likeCount || '0'),
          comment_count: parseInt(statistics.commentCount || '0'),
          tags: snippet.tags || [],
          thumbnail_url: snippet.thumbnails.maxres?.url || snippet.thumbnails.high?.url || snippet.thumbnails.default?.url,
          category_id: snippet.categoryId
        }
      }
    };
  } catch (error: any) {
    // レート制限エラーをチェック
    if (error.response?.status === 429 ||
        error.response?.data?.error?.message?.toLowerCase().includes('quota') ||
        error.message.toLowerCase().includes('quota exceeded')) {
      console.error(`  ❌ YouTube APIレート制限エラー: ${error.response?.data?.error?.message || error.message}`);
      throw new Error('RATE_LIMIT_EXCEEDED');
    }
    console.error(`  ❌ YouTube APIエラー: ${error.response?.data?.error?.message || error.message}`);
    return null;
  }
}

// テキストをチャンク化
function createChunks(text: string, chunkSize: number = 300): string[] {
  if (text.length <= chunkSize) {
    return [text];
  }

  const chunks: string[] = [];
  const sentences = text.split(/(?<=[。.!?])\s*/);
  let currentChunk = '';

  for (const sentence of sentences) {
    if ((currentChunk + sentence).length > chunkSize) {
      if (currentChunk) {
        chunks.push(currentChunk.trim());
        currentChunk = '';
      }

      if (sentence.length > chunkSize) {
        for (let i = 0; i < sentence.length; i += chunkSize) {
          chunks.push(sentence.slice(i, i + chunkSize));
        }
      } else {
        currentChunk = sentence;
      }
    } else {
      currentChunk += sentence;
    }
  }

  if (currentChunk) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
}

// Embeddingを生成
async function generateEmbedding(text: string): Promise<{ embedding: number[] | null; rateLimited: boolean }> {
  try {
    const result = await embeddingModel.embedContent(text);
    return { embedding: result.embedding.values, rateLimited: false };
  } catch (error: any) {
    // レート制限エラーをチェック
    if (error.message.toLowerCase().includes('too many requests') ||
        error.message.toLowerCase().includes('rate limit') ||
        error.message.toLowerCase().includes('quota')) {
      console.error(`    ⚠️ Embeddingレート制限: ${error.message}`);
      return { embedding: null, rateLimited: true };
    }
    console.error(`    ❌ Embedding生成エラー: ${error.message}`);
    return { embedding: null, rateLimited: false };
  }
}

// post_chunksに保存
async function saveChunks(connection: any, postId: string, chunks: Array<{
  text: string;
  index: number;
  media: string;
  source: string;
  type: string;
}>, embeddingRateLimited: { value: boolean }) {
  for (const chunk of chunks) {
    try {
      const chunkId = uuidv7();
      let embeddingVector: number[] | null = null;

      // Embeddingを生成（レート制限が発生していない場合のみ）
      if (!embeddingRateLimited.value) {
        console.log(`    🔄 chunk ${chunk.index}: Embedding生成中...`);
        const result = await generateEmbedding(chunk.text);

        if (result.rateLimited) {
          embeddingRateLimited.value = true;
          console.log(`    ⚠️ 以降の全てのchunkでEmbedding生成をスキップします`);
        } else if (result.embedding) {
          embeddingVector = result.embedding;
          console.log(`    ✅ chunk ${chunk.index}: Embedding生成完了 (${embeddingVector.length}次元)`);
        }
      } else {
        console.log(`    ⏭️ chunk ${chunk.index}: Embedding生成スキップ（レート制限中）`);
      }

      await connection.query(`
        INSERT INTO post_chunks (id, post_id, chunk_index, chunk_text, embedding, metadata, chunk_media, chunk_source, chunk_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
          chunk_text = VALUES(chunk_text),
          embedding = VALUES(embedding),
          metadata = VALUES(metadata),
          chunk_media = VALUES(chunk_media),
          chunk_source = VALUES(chunk_source),
          chunk_type = VALUES(chunk_type)
      `, [
        chunkId,
        postId,
        chunk.index,
        chunk.text,
        embeddingVector ? JSON.stringify(embeddingVector) : null,
        JSON.stringify({
          media: chunk.media,
          source: chunk.source,
          type: chunk.type
        }),
        chunk.media,
        chunk.source,
        chunk.type
      ]);
    } catch (error: any) {
      console.error(`    ❌ チャンク${chunk.index}保存エラー: ${error.message}`);
    }
  }
}

// メイン処理
async function fetchPostsData(startIndex: number, endIndex: number, twitterWaitSeconds: number = 10) {
  console.log(`\n=== 投稿データ取得 (${startIndex}～${endIndex}) ===`);
  console.log(`Twitter待機時間: ${twitterWaitSeconds}秒\n`);

  // SSL設定
  const sslConfig = {
    rejectUnauthorized: false
  };

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT),
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB,
    ssl: sslConfig
  });

  try {
    console.log('✅ データベースに接続しました\n');

    // 指定範囲の投稿を取得（post_numを基準に）
    const [targetPosts]: any = await connection.query(`
      SELECT id, source, title, created_at, post_num
      FROM posts
      WHERE post_num >= ? AND post_num <= ?
      ORDER BY post_num ASC
    `, [startIndex, endIndex]);

    if (targetPosts.length === 0) {
      console.log(`❌ 指定範囲にデータがありません`);
      return;
    }

    console.log(`📋 処理対象: ${targetPosts.length}件の投稿\n`);

    let processedCount = 0;
    let skippedCount = 0;
    let errorCount = 0;
    const embeddingRateLimited = { value: false };

    for (let i = 0; i < targetPosts.length; i++) {
      const post = targetPosts[i];

      console.log(`\n[${post.post_num}/${endIndex}] 処理中...`);
      console.log(`  ID: ${post.id}`);
      console.log(`  URL: ${post.source}`);

      const mediaType = detectMediaType(post.source);
      console.log(`  メディアタイプ: ${mediaType}`);

      if (mediaType === 'Unknown') {
        console.log(`  ⚠️  スキップ: 未対応のメディアタイプ`);
        skippedCount++;
        continue;
      }

      try {
        if (mediaType === 'Twitter') {
          // Twitter処理
          const tweetId = extractTwitterTweetId(post.source);
          if (!tweetId) {
            console.log(`  ❌ Tweet IDを抽出できませんでした`);
            errorCount++;
            continue;
          }

          let twitterData;
          try {
            twitterData = await fetchTwitterData(tweetId);
          } catch (rateLimitError: any) {
            if (rateLimitError.message === 'RATE_LIMIT_EXCEEDED') {
              console.error(`\n\n⛔ レート制限に達しました！`);
              console.error(`処理を停止します。しばらく待ってから再実行してください。`);
              console.error(`\n次回は post_num ${post.post_num} から再開してください。\n`);
              throw rateLimitError;
            }
            throw rateLimitError;
          }
          if (!twitterData) {
            console.log(`  ❌ Twitterデータ取得失敗`);
            errorCount++;
            continue;
          }

          // postsテーブルのmetadataを更新
          await connection.query(`
            UPDATE posts SET metadata = ? WHERE id = ?
          `, [JSON.stringify(twitterData.metadata), post.id]);

          console.log(`  ✅ metadata更新完了`);

          // テキストをチャンク化
          const textChunks = createChunks(twitterData.text);
          const chunks = textChunks.map((text, index) => ({
            text,
            index,
            media: 'Twitter',
            source: 'text_content',
            type: 'twitter_post'
          }));

          await saveChunks(connection, post.id, chunks, embeddingRateLimited);
          console.log(`  ✅ ${chunks.length}個のチャンクを保存`);

          processedCount++;

          // レート制限対策: 指定秒数待機
          if (i < targetPosts.length - 1) {
            console.log(`  ⏳ ${twitterWaitSeconds}秒待機中...`);
            await new Promise(resolve => setTimeout(resolve, twitterWaitSeconds * 1000));
          }

        } else if (mediaType === 'YouTube') {
          // YouTube処理
          const videoId = extractYouTubeVideoId(post.source);
          if (!videoId) {
            console.log(`  ❌ Video IDを抽出できませんでした`);
            errorCount++;
            continue;
          }

          let youtubeData;
          try {
            youtubeData = await fetchYouTubeData(videoId);
          } catch (rateLimitError: any) {
            if (rateLimitError.message === 'RATE_LIMIT_EXCEEDED') {
              console.error(`\n\n⛔ YouTube APIのレート制限に達しました！`);
              console.error(`処理を停止します。しばらく待ってから再実行してください。`);
              console.error(`\n次回は post_num ${post.post_num} から再開してください。\n`);
              throw rateLimitError;
            }
            throw rateLimitError;
          }
          if (!youtubeData) {
            console.log(`  ❌ YouTubeデータ取得失敗`);
            errorCount++;
            continue;
          }

          // postsテーブルのmetadataを更新（titleとdescriptionは除外）
          await connection.query(`
            UPDATE posts SET metadata = ? WHERE id = ?
          `, [JSON.stringify(youtubeData.metadata), post.id]);

          console.log(`  ✅ metadata更新完了`);

          // titleとdescriptionをpost_chunksに保存
          const chunks: Array<any> = [];

          if (youtubeData.title) {
            chunks.push({
              text: youtubeData.title,
              index: 0,
              media: 'YouTube',
              source: 'text_content',
              type: 'youtube_title'
            });
          }

          if (youtubeData.description) {
            chunks.push({
              text: youtubeData.description,
              index: 1,
              media: 'YouTube',
              source: 'text_content',
              type: 'youtube_description'
            });
          }

          await saveChunks(connection, post.id, chunks, embeddingRateLimited);
          console.log(`  ✅ ${chunks.length}個のチャンクを保存`);

          processedCount++;

          // レート制限対策: YouTube APIは1秒待機
          if (i < targetPosts.length - 1) {
            console.log(`  ⏳ 1秒待機中...`);
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        }

      } catch (error: any) {
        if (error.message === 'RATE_LIMIT_EXCEEDED') {
          // レート制限エラーの場合は即座に処理を終了
          console.log(`\n\n=== レート制限により処理を中断 ===`);
          console.log(`処理成功: ${processedCount}`);
          console.log(`スキップ: ${skippedCount}`);
          console.log(`エラー: ${errorCount}`);
          console.log(`\n⚠️  レート制限が解除されるまで待機してください。`);
          console.log(`推奨: 10-15分程度待ってから再実行してください。`);
          return;
        }
        console.error(`  ❌ エラー: ${error.message}`);
        errorCount++;
      }
    }

    console.log(`\n\n=== 処理完了 ===`);
    console.log(`処理成功: ${processedCount}`);
    console.log(`スキップ: ${skippedCount}`);
    console.log(`エラー: ${errorCount}`);

  } finally {
    await connection.end();
    console.log(`\n✅ データベース接続を閉じました`);
  }
}

// コマンドライン引数から範囲を取得
const args = process.argv.slice(2);
if (args.length < 2) {
  console.log('使用方法: npx ts-node scripts/fetchPostsData.ts <開始番号> <終了番号> [Twitter待機秒数]');
  console.log('例: npx ts-node scripts/fetchPostsData.ts 1 10');
  console.log('例: npx ts-node scripts/fetchPostsData.ts 1 10 5  # Twitter待機時間を5秒に設定');
  process.exit(1);
}

const startIndex = parseInt(args[0]);
const endIndex = parseInt(args[1]);
const twitterWaitSeconds = args[2] ? parseInt(args[2]) : 10;

if (isNaN(startIndex) || isNaN(endIndex) || startIndex < 1 || endIndex < startIndex) {
  console.log('❌ 無効な範囲指定です');
  console.log('開始番号と終了番号は1以上の数値で、開始番号 <= 終了番号である必要があります');
  process.exit(1);
}

if (isNaN(twitterWaitSeconds) || twitterWaitSeconds < 0) {
  console.log('❌ 無効な待機時間です');
  console.log('待機時間は0以上の数値である必要があります');
  process.exit(1);
}

fetchPostsData(startIndex, endIndex, twitterWaitSeconds).catch(console.error);
