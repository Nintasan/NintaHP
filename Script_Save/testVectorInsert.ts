import dotenv from 'dotenv';
import mysql from 'mysql2/promise';
import path from 'path';

const envPath = path.resolve(__dirname, '../.env');
dotenv.config({ path: envPath });

async function testVectorInsert() {
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

  console.log('✅ Connected to database\n');

  const postId = '0191ae14-7c98-7774-95b7-e2fcb35303d0'; // post_num = 2

  // テスト用の768次元ベクトル（小さい値で）
  const testVector = Array.from({ length: 768 }, (_, i) => i * 0.001);

  console.log('🧪 Testing different vector insert formats...\n');

  // Format 1: JSON文字列形式
  console.log('--- Test 1: JSON array string format ---');
  try {
    const vectorString = `[${testVector.join(',')}]`;
    console.log('Format:', vectorString.substring(0, 100) + '...');
    await connection.execute(
      'UPDATE posts SET embedding = ? WHERE id = ?',
      [vectorString, postId]
    );
    console.log('✅ Success with JSON array string format\n');

    // 確認
    const [result] = await connection.execute(
      'SELECT embedding IS NOT NULL as has_embedding, VEC_DIMS(embedding) as dims FROM posts WHERE id = ?',
      [postId]
    );
    console.log('Verification:', result);
  } catch (error: any) {
    console.error('❌ Failed:', error.message);
  }

  await connection.end();
}

testVectorInsert().catch(console.error);
