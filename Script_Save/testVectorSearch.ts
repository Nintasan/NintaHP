import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();

/**
 * ベクトル検索の動作確認テスト
 */

async function testVectorSearch() {
  const isTiDBCloud = process.env.DB_HOST?.includes('tidbcloud.com');
  const ssl = isTiDBCloud ? { rejectUnauthorized: true } : undefined;

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT) || 4000,
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB || 's13_l2t',
    ssl: ssl,
  });

  try {
    console.log('=== ベクトル検索テスト ===\n');

    // Step 1: 現在のembedding統計
    console.log('1. embedding統計:');
    const [stats]: any = await (connection as any).query(`
      SELECT
        COUNT(*) as total_chunks,
        SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as null_count,
        SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as has_embedding
      FROM post_chunks
    `);
    console.log('  総チャンク数:', stats[0].total_chunks);
    console.log('  embedding NULL:', stats[0].null_count);
    console.log('  embedding 存在:', stats[0].has_embedding);
    console.log('');

    if (stats[0].has_embedding === 0) {
      console.log('❌ embeddingが存在しません。まずembeddingを生成してください。');
      return;
    }

    // Step 2: サンプルベクトルを取得
    console.log('2. サンプルベクトルを取得中...');
    const [sample]: any = await (connection as any).query(`
      SELECT id, chunk_text, embedding
      FROM post_chunks
      WHERE embedding IS NOT NULL
      LIMIT 1
    `);

    if (sample.length === 0) {
      console.log('❌ embeddingデータが見つかりません');
      return;
    }

    const sampleChunk = sample[0];
    console.log('  チャンクID:', sampleChunk.id);
    console.log('  テキスト:', sampleChunk.chunk_text.substring(0, 100) + '...');
    console.log('  embedding長:', sampleChunk.embedding.length, 'chars');
    console.log('');

    // Step 3: コサイン類似度検索
    console.log('3. コサイン類似度検索（TOP 5）:');
    const startTime = Date.now();
    const [cosineResults]: any = await (connection as any).query(`
      SELECT
        id,
        LEFT(chunk_text, 80) as preview,
        chunk_media,
        chunk_type,
        VEC_COSINE_DISTANCE(embedding, ?) as distance
      FROM post_chunks
      WHERE embedding IS NOT NULL
      ORDER BY distance
      LIMIT 5
    `, [sampleChunk.embedding]);
    const duration = Date.now() - startTime;

    console.log(`  検索時間: ${duration}ms`);
    console.log('  結果:');
    cosineResults.forEach((row: any, i: number) => {
      console.log(`  [${i + 1}] 距離: ${row.distance.toFixed(4)}`);
      console.log(`      メディア: ${row.chunk_media}/${row.chunk_type}`);
      console.log(`      テキスト: ${row.preview}...`);
      console.log('');
    });

    // Step 4: L2距離検索（比較用）
    console.log('4. L2距離検索（TOP 5）:');
    const [l2Results]: any = await (connection as any).query(`
      SELECT
        id,
        LEFT(chunk_text, 80) as preview,
        chunk_media,
        chunk_type,
        VEC_L2_DISTANCE(embedding, ?) as distance
      FROM post_chunks
      WHERE embedding IS NOT NULL
      ORDER BY distance
      LIMIT 5
    `, [sampleChunk.embedding]);

    console.log('  結果:');
    l2Results.forEach((row: any, i: number) => {
      console.log(`  [${i + 1}] 距離: ${row.distance.toFixed(4)}`);
      console.log(`      メディア: ${row.chunk_media}/${row.chunk_type}`);
      console.log(`      テキスト: ${row.preview}...`);
      console.log('');
    });

    // Step 5: インデックス使用確認
    console.log('5. クエリプラン確認（インデックス使用状況）:');
    const [explain]: any = await (connection as any).query(`
      EXPLAIN
      SELECT id, VEC_COSINE_DISTANCE(embedding, ?) as distance
      FROM post_chunks
      WHERE embedding IS NOT NULL
      ORDER BY distance
      LIMIT 5
    `, [sampleChunk.embedding]);

    console.log('  クエリプラン:');
    explain.forEach((row: any) => {
      console.log(`    ${row.id}: ${row.task}`);
    });
    console.log('');

    console.log('✅ ベクトル検索は正常に動作しています！');
    console.log('');
    console.log('使用可能な距離関数:');
    console.log('  - VEC_COSINE_DISTANCE: コサイン類似度（推奨、0=完全一致）');
    console.log('  - VEC_L2_DISTANCE: ユークリッド距離（0=完全一致）');
    console.log('  - VEC_NEGATIVE_INNER_PRODUCT: 内積の負数');
    console.log('');
    console.log('インデックス: idx_embedding_cosine (HNSW)');

  } catch (error: any) {
    console.error('❌ エラー:', error.message);
    throw error;
  } finally {
    await connection.end();
  }
}

testVectorSearch().catch(console.error);
