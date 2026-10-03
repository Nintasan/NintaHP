import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();

async function main() {
  const conn = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '4000'),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB || 's13_l2t',
  });

  const postId = '0191ae14-7c98-7774-95b7-e2fcb35303d0';

  // postsテーブルから基本情報を取得
  const [postRows] = await conn.query(
    'SELECT id, source, ai_title, summary, metadata FROM posts WHERE id = ?',
    [postId]
  );
  console.log('=== POST INFO ===');
  console.log(JSON.stringify(postRows, null, 2));

  // post_chunksから動画解析結果のみを取得
  const [chunkRows] = await conn.query(
    `SELECT chunk_index, chunk_source, chunk_type, chunk_text, metadata
     FROM post_chunks
     WHERE post_id = ? AND chunk_source = 'video_analysis'
     ORDER BY chunk_index`,
    [postId]
  );

  console.log('\n=== VIDEO ANALYSIS CHUNKS ===');
  console.log(`Found ${(chunkRows as any[]).length} video analysis chunks\n`);

  // Fire/flame キーワードをカウント
  let fireCount = 0;
  let flameCount = 0;
  let particleCount = 0;
  let effectCount = 0;
  let riggingCount = 0;

  for (const row of chunkRows as any[]) {
    const text = row.chunk_text.toLowerCase();
    if (text.includes('fire')) fireCount++;
    if (text.includes('flame')) flameCount++;
    if (text.includes('particle')) particleCount++;
    if (text.includes('effect')) effectCount++;
    if (text.includes('rigging') || text.includes('rig')) riggingCount++;

    console.log(`\n--- Chunk ${row.chunk_index} (${row.chunk_type}) ---`);
    console.log(row.chunk_text);
    console.log('');
  }

  console.log('\n=== KEYWORD ANALYSIS ===');
  console.log(`🔥 "fire" mentions: ${fireCount}`);
  console.log(`🔥 "flame" mentions: ${flameCount}`);
  console.log(`✨ "particle" mentions: ${particleCount}`);
  console.log(`✨ "effect" mentions: ${effectCount}`);
  console.log(`🔧 "rigging/rig" mentions: ${riggingCount}`);

  const hasFire = fireCount > 0 || flameCount > 0;
  const hasEffects = particleCount > 0 || effectCount > 0;
  const hasRigging = riggingCount > 0;

  console.log('\n=== VERDICT ===');
  if (hasFire && hasRigging) {
    console.log('✅ SUCCESS: Video analysis correctly identifies FIRE RIGGING content!');
  } else if (hasEffects && hasRigging) {
    console.log('⚠️  PARTIAL: Video analysis identifies effects and rigging, but not specifically fire');
  } else {
    console.log('❌ PROBLEM: Video analysis does not match expected fire rigging content');
    console.log('   Gemini may be analyzing metadata instead of actual video frames');
  }

  await conn.end();
}

main().catch(console.error);
