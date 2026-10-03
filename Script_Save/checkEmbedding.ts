import dotenv from 'dotenv';
import mysql from 'mysql2/promise';
import path from 'path';

// Load environment variables
const envPath = path.resolve(__dirname, '../.env');
dotenv.config({ path: envPath });

async function checkEmbedding() {
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

  // Check posts table structure
  console.log('--- Posts Table Structure ---');
  const [columns] = await connection.query(
    `SHOW COLUMNS FROM posts WHERE Field = 'embedding'`
  );
  console.log(JSON.stringify(columns, null, 2));
  console.log('');

  // Check post_num = 2 embedding data
  console.log('--- Post #2 Embedding Data ---');
  const [posts] = await connection.query(
    `SELECT
      id,
      post_num,
      summary IS NOT NULL as has_summary,
      ai_tags IS NOT NULL as has_ai_tags,
      user_intent IS NOT NULL as has_user_intent,
      embedding IS NOT NULL as has_embedding,
      LENGTH(embedding) as embedding_length,
      LEFT(CAST(embedding AS CHAR), 100) as embedding_preview
    FROM posts
    WHERE post_num = 2`
  );
  console.log(JSON.stringify(posts, null, 2));

  await connection.end();
}

checkEmbedding().catch(console.error);
