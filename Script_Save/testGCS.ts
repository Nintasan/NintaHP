/**
 * GCS接続テストスクリプト
 */

import { Storage } from '@google-cloud/storage';
import dotenv from 'dotenv';
import * as path from 'path';

dotenv.config();

async function testGCS() {
  console.log('='.repeat(70));
  console.log('GCS Connection Test');
  console.log('='.repeat(70));
  console.log('');

  // 環境変数の確認
  console.log('📋 Environment Variables:');
  console.log(`   GOOGLE_APPLICATION_CREDENTIALS: ${process.env.GOOGLE_APPLICATION_CREDENTIALS ? '✅ Set' : '❌ Not set'}`);
  console.log(`   GCS_BUCKET_NAME: ${process.env.GCS_BUCKET_NAME || '❌ Not set'}`);
  console.log('');

  if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    console.error('❌ GOOGLE_APPLICATION_CREDENTIALS is not set in .env');
    process.exit(1);
  }

  if (!process.env.GCS_BUCKET_NAME) {
    console.error('❌ GCS_BUCKET_NAME is not set in .env');
    process.exit(1);
  }

  try {
    // Storage クライアント初期化
    console.log('🔧 Initializing Storage client...');
    const storage = new Storage();
    const bucketName = process.env.GCS_BUCKET_NAME;
    const bucket = storage.bucket(bucketName);

    // サービスアカウント情報の取得
    console.log('');
    console.log('🔑 Service Account Info:');
    const [metadata] = await storage.getServiceAccount();
    console.log(`   Email: ${metadata.emailAddress}`);
    console.log('');

    // バケットの存在確認
    console.log('🪣 Checking bucket existence...');
    const [exists] = await bucket.exists();

    if (!exists) {
      console.error(`❌ Bucket does not exist: gs://${bucketName}`);
      console.log('');
      console.log('📝 Create the bucket with:');
      console.log(`   gsutil mb -p YOUR_PROJECT_ID -c STANDARD -l us-central1 gs://${bucketName}`);
      process.exit(1);
    }

    console.log(`   ✅ Bucket exists: gs://${bucketName}`);
    console.log('');

    // バケットメタデータの取得
    console.log('📊 Bucket Metadata:');
    const [bucketMetadata] = await bucket.getMetadata();
    console.log(`   Location: ${bucketMetadata.location}`);
    console.log(`   Storage Class: ${bucketMetadata.storageClass}`);
    console.log(`   Created: ${bucketMetadata.timeCreated}`);
    console.log('');

    // ファイル一覧の取得
    console.log('📁 Listing files (max 10):');
    const [files] = await bucket.getFiles({ maxResults: 10 });

    if (files.length === 0) {
      console.log('   (Empty - no files in bucket)');
    } else {
      files.forEach(file => {
        const size = file.metadata.size ? Number(file.metadata.size) / 1024 : 0;
        console.log(`   - ${file.name} (${size.toFixed(2)} KB)`);
      });
    }
    console.log('');

    // テストファイルのアップロード
    console.log('📤 Testing upload...');
    const testFileName = `test_${Date.now()}.txt`;
    const testContent = 'GCS connection test successful!';

    const file = bucket.file(testFileName);
    await file.save(testContent, {
      metadata: {
        contentType: 'text/plain',
        metadata: {
          test: 'true',
          timestamp: new Date().toISOString()
        }
      }
    });
    console.log(`   ✅ Uploaded: gs://${bucketName}/${testFileName}`);
    console.log('');

    // テストファイルのダウンロード
    console.log('📥 Testing download...');
    const [downloadedContent] = await file.download();
    const contentMatch = downloadedContent.toString() === testContent;
    console.log(`   ✅ Downloaded: ${downloadedContent.toString()}`);
    console.log(`   Content matches: ${contentMatch ? '✅ Yes' : '❌ No'}`);
    console.log('');

    // テストファイルの削除
    console.log('🗑️  Cleaning up test file...');
    await file.delete();
    console.log(`   ✅ Deleted: gs://${bucketName}/${testFileName}`);
    console.log('');

    // 成功メッセージ
    console.log('='.repeat(70));
    console.log('✅ All GCS tests passed successfully!');
    console.log('='.repeat(70));
    console.log('');
    console.log('You can now use GCS for video analysis with Vertex AI.');
    console.log('');

  } catch (error: any) {
    console.error('');
    console.error('='.repeat(70));
    console.error('❌ GCS Test Failed');
    console.error('='.repeat(70));
    console.error('');
    console.error('Error:', error.message);
    console.error('');

    if (error.code === 'ENOENT') {
      console.error('💡 Possible causes:');
      console.error('   - Service account key file not found');
      console.error('   - Check GOOGLE_APPLICATION_CREDENTIALS path in .env');
    } else if (error.code === 403 || error.message.includes('permission')) {
      console.error('💡 Possible causes:');
      console.error('   - Service account does not have Storage Admin role');
      console.error('   - Run: gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \\');
      console.error('          --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \\');
      console.error('          --role="roles/storage.admin"');
    } else if (error.code === 404 || error.message.includes('Not Found')) {
      console.error('💡 Possible causes:');
      console.error('   - Bucket does not exist');
      console.error(`   - Create it: gsutil mb gs://${process.env.GCS_BUCKET_NAME}`);
    }

    console.error('');
    process.exit(1);
  }
}

testGCS();
