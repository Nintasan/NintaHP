import dotenv from 'dotenv';
import mysql from 'mysql2/promise';
import path from 'path';

// Load environment variables
const envPath = path.resolve(__dirname, '../.env');
dotenv.config({ path: envPath });

async function checkPostData() {
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

  // Check posts table for post_num 1-10
  const [posts] = await connection.query(
    `SELECT
      post_num,
      id,
      source,
      summary IS NOT NULL as has_summary,
      ai_tags IS NOT NULL as has_ai_tags,
      ai_title IS NOT NULL as has_ai_title,
      user_intent IS NOT NULL as has_user_intent,
      ai_processed_at IS NOT NULL as has_ai_processed,
      LEFT(summary, 50) as summary_preview
    FROM posts
    WHERE post_num BETWEEN 1 AND 10
    ORDER BY post_num`
  );

  console.log('📄 Posts Table (post_num 1-10):');
  console.log(JSON.stringify(posts, null, 2));

  await connection.end();
}

checkPostData().catch(console.error);
