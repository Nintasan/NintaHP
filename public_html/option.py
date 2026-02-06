import os
smtp_username = os.environ.get('SMTP_USERNAME', '	info@ninta.main.jp')
smtp_password = os.environ.get('SMTP_PASSWORD', '_69-bwV-1s--ZSaa')
import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask , render_template , request , g , redirect , url_for , session, jsonify
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

bp_option = Blueprint('option', __name__)

@bp_option.route('/option', methods=['POST'])
def option():
    namejp = request.form['namejp']
    nameen = request.form['nameen']
    pricejp = request.form['pricejp']
    priceen = request.form['priceen']
    orders = request.form['orders']
    categories = request.form['categories']

    con = get_db()
    con.execute(
            "INSERT INTO options (NAMEJP, NAMEEN, PRICEJP, PRICEEN, ORDERS, CATEGORIES) VALUES (?, ?, ?, ?, ?, ?)",
            [namejp, nameen, pricejp, priceen, orders, categories]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/updateoption', methods=['POST'])
def updateoption():
    optionid = request.form['id']
    namejp = request.form['namejp']
    nameen = request.form['nameen']
    pricejp = request.form['pricejp']
    priceen = request.form['priceen']
    orders = request.form['orders']
    categories = request.form['categories']

    con = get_db()
    con.execute(
            "UPDATE options SET namejp = ?, nameen = ?, pricejp = ?, priceen = ?, orders = ?, categories = ? WHERE id =?",
            [namejp, nameen, pricejp, priceen, orders, categories, optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/deleteoption', methods=['POST'])
def deleteoption():
    optionid = request.form['id']

    con = get_db()
    con.execute(
            "DELETE FROM options WHERE id = ?",
            [optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/updateorder', methods=['POST'])
def updateorder():
    optionid = request.form['id']
    neworder = request.form['order']

    con = get_db()
    con.execute(
            "UPDATE options SET orders = ? WHERE id =?",
            [neworder, optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/addcolumnoption', methods=['POST'])
def addcolumnoption():
    tablename = request.form['tablename']
    columnname = request.form['columnname']
    types = request.form['type']
    defaults = request.form['default']


    con = get_db()
    query = f"ALTER TABLE {tablename} ADD COLUMN {columnname} {types} DEFAULT {defaults}"
    con.execute(query)
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/plancontent', methods=['POST'])
def plancontent():
    planID = request.form['planID']
    plan1 = request.form['plan1']
    plan2 = request.form['plan2']
    plan3 = request.form['plan3']

    con = get_db()
    con.execute(
            "UPDATE options SET plan1 = ?, plan2 = ?, plan3 = ? WHERE id =?",
            [plan1, plan2, plan3, planID]
        )
    con.commit()
    con.close()

    return redirect(url_for('contact'))

@bp_option.route('/selectoption', methods=['POST'])
def selectoption():
    import sys
    try:
        data = request.get_json()
        if not data:
            sys.stderr.write("ERROR: No JSON data received in /selectoption\n")
            return jsonify({'error': 'No data received'}), 400

        selectoptions0 = data.get('array', [])
        if not selectoptions0:
            sys.stderr.write("WARNING: Empty options array\n")
            return render_template('option.html', selectoptions=[], sumall=(0, 0))

        stmt_formats = ','.join(['?'] * len(selectoptions0))
        con = get_db()
        c = con.cursor()
        c.execute(
            "SELECT * FROM options WHERE id IN(%s) ORDER BY orders" % stmt_formats, tuple(selectoptions0)
        )
        selectoptions = c.fetchall()

        c = con.cursor()
        c.execute(
            "SELECT SUM(pricejp), SUM(priceen) FROM options WHERE id IN(%s)" % stmt_formats, tuple(selectoptions0)
        )
        sumall = c.fetchone()
        con.close()

        return render_template('option.html', selectoptions=selectoptions, sumall=sumall)

    except Exception as e:
        sys.stderr.write(f"ERROR in /selectoption: {str(e)}\n")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@bp_option.route('/sendquotation', methods=['POST'])
def sendquotation():
    import sys
    try:
        data = request.get_json()
        if not data:
            sys.stderr.write("ERROR: No JSON data received\n")
            return jsonify({'success': False, 'error': 'No data received'}), 400

        user_name = data.get('userName')
        user_email = data.get('userEmail')
        quotation_content = data.get('quotationContent')
        message = data.get('message', '')

        sys.stderr.write(f"Received quotation request from {user_name} ({user_email})\n")

        # メール本文を作成
        email_body = f"""
見積依頼 / Quotation Request
================================

お名前 / Name: {user_name}
メールアドレス / Email: {user_email}

{quotation_content}

追加メッセージ / Additional Message:
{message}

================================
このメールは見積フォームから自動送信されました。
This email was sent automatically from the quotation form.
"""

        # MIMEメッセージを作成
        msg = MIMEMultipart()
        msg['From'] = user_email
        msg['To'] = 'ninta.illustration@gmail.com'
        msg['Subject'] = f'見積依頼 / Quotation Request from {user_name}'
        msg['Reply-To'] = user_email

        msg.attach(MIMEText(email_body, 'plain', 'utf-8'))

        # SMTPサーバーに接続してメール送信
        import os

        # 環境変数でSMTPプロバイダーを選択（gmail または lolipop）
        smtp_provider = os.environ.get('SMTP_PROVIDER', 'gmail')

        if smtp_provider == 'gmail':
            # Gmail SMTP設定
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
            smtp_username = os.environ.get('GMAIL_USERNAME', 'ninta.illustration@gmail.com')
            smtp_password = os.environ.get('GMAIL_APP_PASSWORD', 'fenr tslp shpl jdqq')  # Gmailアプリパスワード
            # GmailからGmailに送信
            msg['From'] = smtp_username

            # パスワードが設定されているか確認
            if not smtp_password:
                sys.stderr.write("ERROR: Gmail app password not configured\n")
        else:
            # ロリポップサーバーのSMTP設定
            smtp_server = 'smtp.lolipop.jp'
            smtp_port = 587
            smtp_username = 'info@ninta.main.jp'
            smtp_password = '_69-bwV-1s--ZSaa'

        # デバッグ用：ローカル環境ではメール送信をスキップ
        host = request.host.split(':')[0]  # ポート番号を除去
        is_local = (os.environ.get('FLASK_ENV') == 'development' or
                    host in ['127.0.0.1', 'localhost'] or
                    '127.0.0.1' in request.host or
                    'localhost' in request.host)

        # デバッグログは標準エラー出力に
        sys.stderr.write(f"DEBUG: Host is {request.host}, is_local is {is_local}\n")

        email_sent = False
        if is_local:
            # ローカル環境ではログに出力のみ
            sys.stderr.write("=" * 60 + "\n")
            sys.stderr.write("DEBUG MODE - Email content (not sent):\n")
            sys.stderr.write(f"From: {user_email}\n")
            sys.stderr.write(f"To: ninta.illustration@gmail.com\n")
            sys.stderr.write(f"Subject: 見積依頼 / Quotation Request from {user_name}\n")
            sys.stderr.write("-" * 60 + "\n")
            sys.stderr.write(email_body + "\n")
            sys.stderr.write("=" * 60 + "\n")
            email_sent = True
        else:
            # 本番環境ではメール送信
            try:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
                email_sent = True
                sys.stderr.write("Email sent successfully via SMTP\n")
            except Exception as smtp_error:
                sys.stderr.write(f"SMTP Error: {str(smtp_error)}\n")
                raise  # エラーを上位に伝える

        return jsonify({
            'success': True,
            'message': 'Email sent successfully'
        })

    except Exception as e:
        sys.stderr.write(f"Error sending email: {str(e)}\n")
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500