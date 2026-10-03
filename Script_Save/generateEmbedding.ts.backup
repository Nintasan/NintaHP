/**
 * posts テーブルの embedding カラム生成スクリプト（無料版専用）
 *
 * 使用方法:
 * - 単一のpost_num: npx tsx scripts/generateEmbedding.ts --post-num=123
 * - 範囲指定: npx tsx scripts/generateEmbedding.ts --from=100 --to=200
 *
 * 機能:
 * - post_num を指定して、該当ポストの summary, ai_tags, user_intent を結合
 * - Google AI Studio の gemini-embedding-001 (768次元) でベクトル化
 * - embedding カラムに VECTOR型で保存
 *
 * 制限:
 * - 無料版: 1日1000リクエストまで
 * - 1000件を超える場合は複数日に分けて実行
 */

import mysql from 'mysql2/promise';
import dotenv from 'dotenv';
import { GoogleGenerativeAI } from '@google/generative-ai';

dotenv.config();

// Google AI Studio API設定
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

// MySQL 接続設定
const isTiDBCloud = process.env.DB_HOST?.includes('tidbcloud.com');
const dbConfig = {
  host: process.env.DB_HOST || process.env.DATABASE_HOST || 'localhost',
  port: Number(process.env.DB_PORT || process.env.DATABASE_PORT) || 4000,
  user: process.env.DB_USER || process.env.DATABASE_USER || 'root',
  password: process.env.DB_PASSWORD || process.env.DATABASE_PASSWORD || '',
  database: process.env.DB || process.env.DATABASE_NAME || 's13_l2t',
  ssl: isTiDBCloud ? { rejectUnauthorized: true } : undefined,
};

interface PostData {
  id: string;
  post_num: number;
  summary: string | null;
  ai_tags: string | null;
  user_intent: string | null;
  embedding: any;
}

/**
 * レート制限エラーかどうかを判定
 */
function isRateLimitError(error: any): boolean {
  const errorMessage = error.message?.toLowerCase() || '';
  return (
    errorMessage.includes('rate limit') ||
    errorMessage.includes('quota exceeded') ||
    errorMessage.includes('resource exhausted') ||
    errorMessage.includes('429') ||
    error.status === 429
  );
}

/**
 * テキストをベクトル化する（リトライ機能付き）
 */
async function generateEmbedding(text: string, retries = 3): Promise<number[]> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const model = genAI.getGenerativeModel({
        model: 'gemini-embedding-001',
      });

      const result = await model.embedContent({
        content: { parts: [{ text }] },
        taskType: 'RETRIEVAL_DOCUMENT',
        outputDimensionality: 768, // 768次元を明示的に指定
      });

      return result.embedding.values;
    } catch (error: any) {
      const isLastAttempt = attempt === retries;

      // レート制限エラーの場合
      if (isRateLimitError(error)) {
        if (isLastAttempt) {
          console.error(`   ❌ レート制限に達しました。1日の無料枠（1000件）を使い切った可能性があります。`);
          console.error(`   💡 明日再実行するか、処理を1000件以下に分けてください。`);
          throw error;
        }

        // 指数バックオフで待機
        const waitTime = Math.min(5000 * Math.pow(2, attempt - 1), 60000);
        console.log(`   ⏳ レート制限: ${waitTime / 1000}秒待機後にリトライ (${attempt}/${retries})...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
        continue;
      }

      // その他のエラー
      console.error(`   ❌ Embedding generation failed (attempt ${attempt}/${retries}): ${error.message}`);

      if (isLastAttempt) {
        throw error;
      }

      // 短い待機後にリトライ
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }

  throw new Error('Failed to generate embedding after all retries');
}

/**
 * post_num から summary, ai_tags, user_intent を取得
 */
async function getPostData(connection: mysql.Connection, postNum: number): Promise<PostData | null> {
  const [rows] = await connection.execute<mysql.RowDataPacket[]>(
    'SELECT id, post_num, summary, ai_tags, user_intent, embedding FROM posts WHERE post_num = ?',
    [postNum]
  );

  if (rows.length === 0) {
    return null;
  }

  return rows[0] as PostData;
}

/**
 * post_num の範囲でポストを取得
 */
async function getPostsInRange(
  connection: mysql.Connection,
  fromPostNum: number,
  toPostNum: number
): Promise<PostData[]> {
  const [rows] = await connection.execute<mysql.RowDataPacket[]>(
    'SELECT id, post_num, summary, ai_tags, user_intent, embedding FROM posts WHERE post_num BETWEEN ? AND ? ORDER BY post_num',
    [fromPostNum, toPostNum]
  );

  return rows as PostData[];
}

/**
 * embedding を posts テーブルに保存（VECTOR型として保存）
 */
async function saveEmbedding(
  connection: mysql.Connection,
  postId: string,
  embedding: number[]
): Promise<void> {
  // VECTOR型のフォーマット: [1.0,2.0,3.0,...]
  const vectorString = `[${embedding.join(',')}]`;
  await connection.execute(
    'UPDATE posts SET embedding = ? WHERE id = ?',
    [vectorString, postId]
  );
}

/**
 * ai_tags を文字列に変換
 */
function aiTagsToString(aiTags: any): string {
  if (!aiTags) return '';

  // すでに配列の場合
  if (Array.isArray(aiTags)) {
    return aiTags.join(', ');
  }

  // 文字列の場合
  if (typeof aiTags === 'string') {
    try {
      // JSON文字列の可能性があるのでパース試行
      const parsed = JSON.parse(aiTags);
      if (Array.isArray(parsed)) {
        return parsed.join(', ');
      }
      return aiTags;
    } catch {
      // JSONパースに失敗したらそのまま返す
      return aiTags;
    }
  }

  return '';
}

/**
 * 単一のポストを処理
 */
async function processSinglePost(connection: mysql.Connection, postData: PostData): Promise<boolean> {
  try {
    const aiTagsStr = aiTagsToString(postData.ai_tags);

    console.log(`\n📝 Processing post_num: ${postData.post_num} (${postData.id})`);
    console.log(`   Summary: ${postData.summary?.substring(0, 50) || 'N/A'}...`);
    console.log(`   AI Tags: ${aiTagsStr.substring(0, 50) || 'N/A'}...`);
    console.log(`   User Intent: ${postData.user_intent?.substring(0, 50) || 'N/A'}...`);

    // summary, ai_tags, user_intent の結合
    const combinedText = [
      postData.summary || '',
      aiTagsStr,
      postData.user_intent || ''
    ]
      .filter(Boolean)
      .join('\n\n');

    if (!combinedText.trim()) {
      console.log('   ⚠️  Skipped: No data available for embedding');
      return false;
    }

    // ベクトル化
    const embedding = await generateEmbedding(combinedText);
    console.log(`   ✅ Embedding generated (dimension: ${embedding.length})`);

    // DB 保存
    await saveEmbedding(connection, postData.id, embedding);
    console.log(`   💾 Saved to database`);

    return true;
  } catch (error: any) {
    // レート制限エラーの場合は再スロー（上位で処理）
    if (isRateLimitError(error)) {
      throw error;
    }
    console.error(`   ❌ Error: ${error.message}`);
    return false;
  }
}

/**
 * メイン処理
 */
async function main() {
  // コマンドライン引数の取得
  const args = process.argv.slice(2);
  const postNumArg = args.find((arg) => arg.startsWith('--post-num='));
  const fromArg = args.find((arg) => arg.startsWith('--from='));
  const toArg = args.find((arg) => arg.startsWith('--to='));

  // 引数チェック
  if (!postNumArg && (!fromArg || !toArg)) {
    console.error('❌ Usage:');
    console.error('  Single post: npx tsx scripts/generateEmbedding.ts --post-num=<post_num>');
    console.error('  Range: npx tsx scripts/generateEmbedding.ts --from=<start> --to=<end>');
    console.error('');
    console.error('💡 Note: 無料版は1日1000リクエストまで。1000件を超える場合は複数日に分けてください。');
    process.exit(1);
  }

  // DB 接続
  const connection = await mysql.createConnection(dbConfig);

  try {
    // 単一のpost_num処理
    if (postNumArg) {
      const postNum = parseInt(postNumArg.split('=')[1], 10);

      if (isNaN(postNum)) {
        console.error('❌ Invalid post_num. Please provide a valid number.');
        process.exit(1);
      }

      console.log(`🚀 Starting embedding generation for post_num: ${postNum}`);
      console.log(`📍 Using: Google AI Studio (gemini-embedding-001, 768 dimensions)\n`);

      const postData = await getPostData(connection, postNum);

      if (!postData) {
        console.error(`❌ Post with post_num ${postNum} not found.`);
        process.exit(1);
      }

      const success = await processSinglePost(connection, postData);

      if (success) {
        console.log('\n✅ Complete!');
      } else {
        console.log('\n⚠️  Completed with warnings');
      }
    }
    // 範囲処理
    else {
      const fromPostNum = parseInt(fromArg!.split('=')[1], 10);
      const toPostNum = parseInt(toArg!.split('=')[1], 10);

      if (isNaN(fromPostNum) || isNaN(toPostNum)) {
        console.error('❌ Invalid range. Please provide valid numbers.');
        process.exit(1);
      }

      if (fromPostNum > toPostNum) {
        console.error('❌ Invalid range. --from must be less than or equal to --to');
        process.exit(1);
      }

      const rangeSize = toPostNum - fromPostNum + 1;
      if (rangeSize > 1000) {
        console.warn('⚠️  警告: 範囲が1000件を超えています。無料版の1日の制限（1000件）を超える可能性があります。');
        console.warn('💡 推奨: 1000件以下に分けて実行してください。\n');
      }

      console.log(`🚀 Starting embedding generation for post_num range: ${fromPostNum} to ${toPostNum}`);
      console.log(`📍 Using: Google AI Studio (gemini-embedding-001, 768 dimensions)`);
      console.log(`📊 Range size: ${rangeSize} posts\n`);

      const posts = await getPostsInRange(connection, fromPostNum, toPostNum);

      if (posts.length === 0) {
        console.error(`❌ No posts found in range ${fromPostNum} to ${toPostNum}`);
        process.exit(1);
      }

      console.log(`📊 Found ${posts.length} posts to process\n`);

      let successCount = 0;
      let skipCount = 0;
      let errorCount = 0;
      let quotaExceeded = false;

      for (let i = 0; i < posts.length; i++) {
        console.log(`[${i + 1}/${posts.length}]`);

        try {
          const success = await processSinglePost(connection, posts[i]);

          if (success) {
            successCount++;
          } else {
            skipCount++;
          }
        } catch (error: any) {
          // レート制限エラーの場合、処理を中断
          if (isRateLimitError(error)) {
            console.error(`\n❌ 無料版の1日の制限（1000件）に達しました。`);
            console.error(`📊 処理済み: ${successCount + skipCount + errorCount} / ${posts.length}`);
            console.error(`💡 明日、post_num=${posts[i].post_num} から再開してください。\n`);
            quotaExceeded = true;
            break;
          }

          // その他のエラーはカウントして継続
          console.error(`   ❌ Unhandled error for post_num=${posts[i].post_num}: ${error.message}`);
          errorCount++;
        }

        // レート制限対策: 少し待機
        if (i < posts.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      console.log('\n========================================');
      if (quotaExceeded) {
        console.log('⚠️  Quota exceeded - Partial completion');
      } else {
        console.log('✅ Batch processing complete!');
      }
      console.log(`   Total: ${posts.length}`);
      console.log(`   Success: ${successCount}`);
      console.log(`   Skipped: ${skipCount}`);
      console.log(`   Errors: ${errorCount}`);
      console.log('========================================');
    }
  } catch (error: any) {
    console.error('❌ Error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  } finally {
    await connection.end();
  }
}

main();
