# メール通知設定ガイド / Email Notification Setup Guide

フォームからの問い合わせをGmailで受信するための設定方法です。

## 手順 / Steps

### 1. Googleアカウントで2段階認証を有効化

1. Googleアカウントにログイン
2. https://myaccount.google.com/security にアクセス
3. 「2段階認証プロセス」をクリック
4. 指示に従って2段階認証を有効化

### 2. アプリパスワードを生成

1. https://myaccount.google.com/apppasswords にアクセス
   - または、Googleアカウント → セキュリティ → 2段階認証プロセス → アプリパスワード
2. 「アプリを選択」で「メール」を選択
3. 「デバイスを選択」で「その他（名前を入力）」を選択
4. 名前に「Ninta Website」など入力
5. 「生成」をクリック
6. **16文字のパスワードが表示されます（スペースなし）** - これをコピー

### 3. email_config.py を設定

`public_html/email_config.py` を開いて編集:

```python
# Googleアプリパスワード（通常のパスワードではありません）
EMAIL_PASSWORD = "ここに16文字のアプリパスワードを貼り付け"

# メール送信の有効/無効
EMAIL_ENABLED = True  # Falseから Trueに変更
```

**例:**
```python
EMAIL_PASSWORD = "abcd efgh ijkl mnop"  # 実際のアプリパスワードを入力
EMAIL_ENABLED = True
```

### 4. 動作確認

1. Flaskサーバーを再起動
2. Webサイトのお問い合わせフォームからテスト送信
3. ninta.illustration@gmail.com にメールが届くことを確認

## トラブルシューティング

### メールが届かない場合

1. **アプリパスワードが正しいか確認**
   - 16文字すべて入力されているか
   - スペースは不要（あってもOK）

2. **EMAIL_ENABLED が True になっているか確認**
   ```python
   EMAIL_ENABLED = True
   ```

3. **2段階認証が有効になっているか確認**
   - 2段階認証なしではアプリパスワードは作成できません

4. **エラーログを確認**
   - Flaskの実行ログに `Email sending failed:` というメッセージがないか確認

5. **Gmailの受信トレイとスパムフォルダを確認**
   - スパムフォルダに振り分けられている可能性があります

### セキュリティに関する注意

- **email_config.py は絶対にGitにコミットしないでください**
- アプリパスワードは通常のパスワードと同様に厳重に管理してください
- 不要になったアプリパスワードは削除してください

## .gitignore に追加（推奨）

```
email_config.py
```

これで設定完了です！フォームからの問い合わせが ninta.illustration@gmail.com に届くようになります。
