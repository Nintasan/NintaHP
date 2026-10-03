import dotenv from 'dotenv';
import mysql from 'mysql2/promise';
import path from 'path';

// Load environment variables
const envPath = path.resolve(__dirname, '../.env');
dotenv.config({ path: envPath });

async function migrateToVector() {
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

  console.log('✅ Connected to database');
  console.log(`📊 Host: ${process.env.DB_HOST}`);
  console.log(`📊 Database: ${process.env.DB}`);
  console.log('');

  try {
    // 1. postsテーブルのembeddingカラムを確認
    console.log('🔍 Checking current embedding column type...');
    const [currentType] = await connection.query(
      `SHOW COLUMNS FROM posts WHERE Field = 'embedding'`
    );
    console.log('Current type:', JSON.stringify(currentType, null, 2));
    console.log('');

    // 2. JSONデータをバックアップ（既存データがある場合）
    console.log('💾 Backing up existing embedding data...');
    const [existingData] = await connection.query(
      `SELECT COUNT(*) as count FROM posts WHERE embedding IS NOT NULL`
    );
    console.log(`Found ${(existingData as any)[0].count} posts with existing embedding data`);
    console.log('');

    // 3. embeddingカラムを削除
    console.log('🗑️  Dropping existing embedding column...');
    await connection.query(`ALTER TABLE posts DROP COLUMN IF EXISTS embedding`);
    console.log('✅ Dropped embedding column');
    console.log('');

    // 4. VECTOR型でembeddingカラムを追加
    console.log('➕ Adding VECTOR(768) embedding column...');
    await connection.query(
      `ALTER TABLE posts ADD COLUMN embedding VECTOR(768) DEFAULT NULL COMMENT 'AI検索用のベクトルデータ（summary, ai_tags, user_intentから生成）'`
    );
    console.log('✅ Added VECTOR(768) embedding column');
    console.log('');

    // 5. ベクトル検索用のインデックスを追加（オンデマンドでカラムナーレプリカを作成）
    console.log('🔍 Adding vector search index...');
    try {
      await connection.query(
        `ALTER TABLE posts ADD VECTOR INDEX idx_posts_embedding ((VEC_L2_DISTANCE(embedding))) ADD_COLUMNAR_REPLICA_ON_DEMAND COMMENT 'L2距離ベースのベクトル検索インデックス'`
      );
      console.log('✅ Added vector search index');
    } catch (error: any) {
      console.warn('⚠️  Could not add vector index:', error.message);
      console.warn('   You can add it manually later or use application-level similarity search');
    }
    console.log('');

    // 6. post_chunksテーブルも同様に処理
    console.log('🔄 Migrating post_chunks table...');
    await connection.query(`ALTER TABLE post_chunks DROP COLUMN IF EXISTS embedding`);
    await connection.query(
      `ALTER TABLE post_chunks ADD COLUMN embedding VECTOR(768) DEFAULT NULL COMMENT 'chunk_textのベクトルデータ（Gemini APIで生成）'`
    );
    try {
      await connection.query(
        `ALTER TABLE post_chunks ADD VECTOR INDEX idx_post_chunks_embedding ((VEC_L2_DISTANCE(embedding))) ADD_COLUMNAR_REPLICA_ON_DEMAND COMMENT 'L2距離ベースのベクトル検索インデックス'`
      );
      console.log('✅ Migrated post_chunks table with vector index');
    } catch (error: any) {
      console.warn('⚠️  Could not add vector index to post_chunks:', error.message);
      console.log('✅ Migrated post_chunks table (without index)');
    }
    console.log('');

    // 7. 変更を確認
    console.log('📊 Verifying migration...');
    const [newType] = await connection.query(
      `SHOW COLUMNS FROM posts WHERE Field = 'embedding'`
    );
    console.log('New posts.embedding type:', JSON.stringify(newType, null, 2));

    const [chunksType] = await connection.query(
      `SHOW COLUMNS FROM post_chunks WHERE Field = 'embedding'`
    );
    console.log('New post_chunks.embedding type:', JSON.stringify(chunksType, null, 2));
    console.log('');

    console.log('========================================');
    console.log('✅ Migration completed successfully!');
    console.log('========================================');
    console.log('');
    console.log('⚠️  Note: All existing embedding data has been cleared.');
    console.log('Please run the embedding generation script to regenerate embeddings.');
    console.log('');
    console.log('Example:');
    console.log('  npx tsx scripts/generateEmbedding.ts --from=1 --to=100');

  } catch (error: any) {
    console.error('❌ Migration failed:', error.message);
    throw error;
  } finally {
    await connection.end();
  }
}

migrateToVector().catch(console.error);
