import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();

async function clearAIData() {
  console.log('=== AI生成データのクリア開始 ===\n');

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT) || 4000,
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 's13_l2t',
  });

  try {
    console.log('✅ DB接続成功\n');

    // 1. post_chunksテーブルをクリア
    console.log('【1/3】 post_chunksテーブルをクリア中...');
    const [chunkResult] = await connection.query('DELETE FROM post_chunks');
    console.log(`✅ ${(chunkResult as any).affectedRows}件のチャンクを削除\n`);

    // 2. postsテーブルのAI関連フィールドをクリア
    console.log('【2/3】 postsテーブルのAI関連フィールドをクリア中...');
    const [postResult] = await connection.query(`
      UPDATE posts
      SET
        ai_title = NULL,
        ai_tags = NULL,
        user_intent = NULL,
        total_chunks = NULL,
        ai_processed_at = NULL
    `);
    console.log(`✅ ${(postResult as any).affectedRows}件のポストのAIデータをクリア\n`);

    // 3. 確認
    console.log('【3/3】 クリア結果を確認...');
    const [postCount] = await connection.query<mysql.RowDataPacket[]>(
      'SELECT COUNT(*) as count FROM posts'
    );
    const [chunkCount] = await connection.query<mysql.RowDataPacket[]>(
      'SELECT COUNT(*) as count FROM post_chunks'
    );
    const [aiCount] = await connection.query<mysql.RowDataPacket[]>(
      'SELECT COUNT(*) as count FROM posts WHERE ai_processed_at IS NOT NULL'
    );

    console.log(`総ポスト数: ${postCount[0].count}件`);
    console.log(`残りチャンク数: ${chunkCount[0].count}件`);
    console.log(`AI処理済みポスト数: ${aiCount[0].count}件`);

    console.log('\n=== クリア完了 ===');
  } catch (error: any) {
    console.error('❌ エラー:', error.message);
  } finally {
    await connection.end();
    console.log('\nDB接続を閉じました');
  }
}

clearAIData();
