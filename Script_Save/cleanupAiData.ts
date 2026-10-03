/**
 * AI解析データクリーンアップスクリプト（本番環境対応）
 *
 * - postsテーブルのAI関連カラムをNULLに設定
 * - post_chunksテーブルの全データを削除
 *
 * 使い方:
 *   npx tsx scripts/cleanupAiData.ts
 *
 * オプション:
 *   --confirm: 確認プロンプトをスキップ
 *   --dry-run: 実行せずに削除対象を表示
 *
 * 例:
 *   npx tsx scripts/cleanupAiData.ts --dry-run
 *   npx tsx scripts/cleanupAiData.ts --confirm
 */

import mysql from 'mysql2/promise';
import dotenv from 'dotenv';
import * as readline from 'readline';

dotenv.config();

const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run');
const skipConfirm = args.includes('--confirm');

async function askConfirmation(question: string): Promise<boolean> {
  if (skipConfirm) return true;

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(`${question} (yes/no): `, (answer) => {
      rl.close();
      resolve(answer.toLowerCase() === 'yes' || answer.toLowerCase() === 'y');
    });
  });
}

async function main() {
  console.log('='.repeat(70));
  console.log('AI Data Cleanup Script');
  console.log('='.repeat(70));
  console.log('');

  if (isDryRun) {
    console.log('🔍 DRY RUN MODE - No data will be deleted');
    console.log('');
  }

  // データベース接続情報を表示
  console.log('📊 Database Configuration:');
  console.log(`   Host: ${process.env.DB_HOST || 'localhost'}`);
  console.log(`   Port: ${process.env.DB_PORT || '4000'}`);
  console.log(`   Database: ${process.env.DB || 's13_l2t'}`);
  console.log(`   User: ${process.env.DB_USER || 'root'}`);
  console.log('');

  // データベース接続
  const isTiDBCloud = process.env.DB_HOST?.includes('tidbcloud.com');
  const ssl = isTiDBCloud ? { rejectUnauthorized: true } : undefined;

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '4000'),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB || 's13_l2t',
    ssl: ssl,
  });

  try {
    // 削除対象データの確認
    console.log('📋 Checking current data...');
    console.log('');

    const [postChunksCount] = await connection.query(
      'SELECT COUNT(*) as count FROM post_chunks'
    );
    const postChunksTotal = (postChunksCount as any[])[0].count;

    const [postsWithAiData] = await connection.query(`
      SELECT COUNT(*) as count FROM posts
      WHERE ai_processed_at IS NOT NULL
         OR summary IS NOT NULL
         OR ai_tags IS NOT NULL
         OR ai_title IS NOT NULL
    `);
    const postsWithAiTotal = (postsWithAiData as any[])[0].count;

    const [allPostsCount] = await connection.query('SELECT COUNT(*) as count FROM posts');
    const totalPosts = (allPostsCount as any[])[0].count;

    console.log('Current Status:');
    console.log(`   Total posts: ${totalPosts}`);
    console.log(`   Posts with AI data: ${postsWithAiTotal}`);
    console.log(`   Post chunks: ${postChunksTotal}`);
    console.log('');

    if (postChunksTotal === 0 && postsWithAiTotal === 0) {
      console.log('✅ No AI data found. Nothing to clean up.');
      await connection.end();
      process.exit(0);
    }

    // Dry run モード
    if (isDryRun) {
      console.log('='.repeat(70));
      console.log('🔍 DRY RUN SUMMARY:');
      console.log('='.repeat(70));
      console.log(`Will delete ${postChunksTotal} rows from post_chunks`);
      console.log(`Will clear AI data from ${postsWithAiTotal} posts`);
      console.log('');
      console.log('To execute, run without --dry-run:');
      console.log('  npx tsx scripts/cleanupAiData.ts');
      console.log('');
      await connection.end();
      process.exit(0);
    }

    // 確認プロンプト
    console.log('⚠️  WARNING: This will:');
    console.log(`   - Delete ${postChunksTotal} rows from post_chunks table`);
    console.log(`   - Clear AI data from ${postsWithAiTotal} posts`);
    console.log('');
    console.log('This action CANNOT be undone!');
    console.log('');

    const confirmed = await askConfirmation('Are you sure you want to proceed?');

    if (!confirmed) {
      console.log('');
      console.log('❌ Cleanup cancelled by user');
      await connection.end();
      process.exit(0);
    }

    console.log('');
    console.log('Starting cleanup...');
    console.log('');

    // Step 1: post_chunksテーブルのデータを削除
    console.log('Step 1: Deleting all data from post_chunks table...');
    const [deleteResult] = await connection.query('DELETE FROM post_chunks');
    const deletedRows = (deleteResult as any).affectedRows;
    console.log(`   ✅ Deleted ${deletedRows} rows from post_chunks`);
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
    console.log(`   ✅ Cleared AI data from ${updatedRows} posts`);
    console.log('');

    // Step 3: 確認クエリ
    console.log('Step 3: Verification...');
    const [postChunksCountAfter] = await connection.query(
      'SELECT COUNT(*) as count FROM post_chunks'
    );
    const [postsWithAiDataAfter] = await connection.query(`
      SELECT COUNT(*) as count FROM posts
      WHERE summary IS NOT NULL
         OR ai_tags IS NOT NULL
         OR ai_title IS NOT NULL
         OR user_intent IS NOT NULL
         OR metadata IS NOT NULL
         OR embedding IS NOT NULL
    `);

    console.log(`   post_chunks count: ${(postChunksCountAfter as any[])[0].count}`);
    console.log(`   posts with AI data: ${(postsWithAiDataAfter as any[])[0].count}`);
    console.log('');

    if ((postChunksCountAfter as any[])[0].count === 0 && (postsWithAiDataAfter as any[])[0].count === 0) {
      console.log('='.repeat(70));
      console.log('✅ Cleanup completed successfully!');
      console.log('='.repeat(70));
      console.log('');
      console.log('Summary:');
      console.log(`   - Deleted ${deletedRows} post chunks`);
      console.log(`   - Cleared AI data from ${updatedRows} posts`);
      console.log('');
      console.log('You can now run AI analysis again:');
      console.log('  npx ts-node scripts/generateAiSearchData.ts --skip-processed');
      console.log('');
    } else {
      console.warn('⚠️  Some data may still exist. Please verify manually.');
    }

    await connection.end();
    process.exit(0);
  } catch (error) {
    console.error('');
    console.error('❌ Cleanup failed:', error);
    console.error('');
    await connection.end();
    process.exit(1);
  }
}

main();
