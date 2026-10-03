/**
 * テスト用にpostsテーブルとpost_chunksテーブルをクリーンアップするスクリプト
 *
 * - postsテーブルのAI関連カラム（summary, ai_tags, total_chunks, ai_processed_at, ai_title, user_intent, metadata, embedding）をNULLに設定
 * - post_chunksテーブルの全データを削除
 *
 * 使い方:
 *   npx tsx scripts/cleanupPostsForTesting.ts
 *
 * 注意: このスクリプトはローカル環境でのみ実行してください
 */

import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();

async function main() {
  console.log('='.repeat(60));
  console.log('Cleanup Posts and Post Chunks for Testing');
  console.log('='.repeat(60));
  console.log('');

  // 環境チェック
  if (process.env.ENV !== 'local') {
    console.error('❌ This script should only be run in LOCAL environment!');
    console.error(`   Current ENV: ${process.env.ENV}`);
    console.error('');
    console.error('To proceed, ensure ENV=local in your .env file');
    process.exit(1);
  }

  console.log('⚠️  WARNING: This will delete AI-related data from posts and all post_chunks!');
  console.log('');

  // データベース接続
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '4000'),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB || 's13_l2t',
  });

  try {
    // Step 1: post_chunksテーブルのデータを削除
    console.log('Step 1: Deleting all data from post_chunks table...');
    const [deleteResult] = await connection.query('DELETE FROM post_chunks');
    const deletedRows = (deleteResult as any).affectedRows;
    console.log(`✅ Deleted ${deletedRows} rows from post_chunks`);
    console.log('');

    // Step 2: postsテーブルのAI関連カラムをNULLに設定
    console.log('Step 2: Clearing AI-related columns in posts table...');
    const [updateResult] = await connection.query(`
      UPDATE posts
      SET
        summary = NULL,
        ai_tags = NULL,
        total_chunks = 0,
        ai_processed_at = NULL,
        ai_title = NULL,
        user_intent = NULL,
        metadata = NULL,
        embedding = NULL
    `);
    const updatedRows = (updateResult as any).affectedRows;
    console.log(`✅ Cleared AI data from ${updatedRows} posts`);
    console.log('');

    // Step 3: 確認クエリ
    console.log('Step 3: Verification...');
    const [postChunksCount] = await connection.query(
      'SELECT COUNT(*) as count FROM post_chunks'
    );
    const [postsWithAiData] = await connection.query(`
      SELECT COUNT(*) as count FROM posts
      WHERE summary IS NOT NULL
         OR ai_tags IS NOT NULL
         OR ai_title IS NOT NULL
         OR user_intent IS NOT NULL
         OR metadata IS NOT NULL
         OR embedding IS NOT NULL
    `);

    console.log(`post_chunks count: ${(postChunksCount as any[])[0].count}`);
    console.log(`posts with AI data: ${(postsWithAiData as any[])[0].count}`);
    console.log('');

    if ((postChunksCount as any[])[0].count === 0 && (postsWithAiData as any[])[0].count === 0) {
      console.log('='.repeat(60));
      console.log('✅ Cleanup completed successfully!');
      console.log('='.repeat(60));
      console.log('');
      console.log('You can now test URL-based metadata and chunk generation.');
      console.log('');
    } else {
      console.warn('⚠️  Some data may still exist. Please verify manually.');
    }

    await connection.end();
    process.exit(0);
  } catch (error) {
    console.error('❌ Cleanup failed:', error);
    await connection.end();
    process.exit(1);
  }
}

main();
