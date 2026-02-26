import sqlite3
import json
from flask import Flask , render_template , request , g , redirect , url_for , session , flash, current_app, send_file, abort, make_response, jsonify
from datetime import timedelta, datetime
from signup import bp_signup
from login import bp_login
from tag import bp_tag
from userpage import bp_userpage
from db import bp_db
from db import UpdatePosts
from db import get_db
from db import optiondb
from option import bp_option
from functools import wraps
from collections import defaultdict
import os
import time


app = Flask(__name__)
app.register_blueprint(bp_signup)
app.register_blueprint(bp_login)
app.register_blueprint(bp_tag)
app.register_blueprint(bp_userpage)
app.register_blueprint(bp_db)
app.register_blueprint(bp_option)



app.secret_key = "aaa"
app.permanent_session_lifetime = timedelta(minutes=120)

# ================== Security Protection Layer ==================

# Rate limiting storage (IP -> [timestamp, count])
rate_limit_storage = defaultdict(lambda: {'requests': [], 'blocked_until': None})

# Suspicious activity log
suspicious_activity_log = []

def check_rate_limit(ip_address, max_requests=30, time_window=60):
    """
    Rate limiting: max_requests per time_window seconds
    Returns: (is_allowed, retry_after)
    """
    now = time.time()
    client_data = rate_limit_storage[ip_address]

    # Check if IP is temporarily blocked
    if client_data['blocked_until'] and now < client_data['blocked_until']:
        retry_after = int(client_data['blocked_until'] - now)
        return False, retry_after

    # Clean old requests outside time window
    client_data['requests'] = [req_time for req_time in client_data['requests']
                                if now - req_time < time_window]

    # Check if rate limit exceeded
    if len(client_data['requests']) >= max_requests:
        # Block for 5 minutes
        client_data['blocked_until'] = now + 300
        log_suspicious_activity(ip_address, 'RATE_LIMIT_EXCEEDED',
                                f'{len(client_data["requests"])} requests in {time_window}s')
        return False, 300

    # Add current request
    client_data['requests'].append(now)
    return True, 0

def log_suspicious_activity(ip_address, activity_type, details):
    """Log suspicious activity for monitoring"""
    suspicious_activity_log.append({
        'timestamp': datetime.now().isoformat(),
        'ip': ip_address,
        'type': activity_type,
        'details': details,
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    })

    # Keep only last 1000 entries
    if len(suspicious_activity_log) > 1000:
        suspicious_activity_log.pop(0)

def is_suspicious_user_agent(user_agent):
    """Detect suspicious user agents (download tools, scrapers, bots)"""
    if not user_agent:
        return True

    user_agent_lower = user_agent.lower()

    # Known download tools and scraper patterns
    suspicious_patterns = [
        'wget', 'curl', 'scrapy', 'bot', 'spider', 'crawler',
        'download', 'fetcher', 'python-requests', 'java/',
        'libwww', 'http_request', 'httpclient', 'go-http-client',
        'httrack', 'teleport', 'webcopier', 'mass downloader'
    ]

    return any(pattern in user_agent_lower for pattern in suspicious_patterns)

@app.before_request
def security_checks():
    """Run security checks before each request"""
    # Get real IP address
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address:
        ip_address = ip_address.split(',')[0].strip()

    # Skip security checks for localhost development
    is_localhost = ip_address in ['127.0.0.1', 'localhost', '::1']

    # 1. Rate limiting check (skip for localhost)
    if not is_localhost:
        # Normal requests: 30 per minute
        is_allowed, retry_after = check_rate_limit(ip_address, max_requests=30, time_window=60)
        if not is_allowed:
            response = make_response('Too Many Requests - Rate limit exceeded', 429)
            response.headers['Retry-After'] = str(retry_after)
            return response

    # 2. Block admin routes for non-admin users
    if request.path.startswith('/admin/'):
        if 'username' not in session:
            flash('ログインが必要です / Login required')
            return redirect(url_for('login.login'))
        if session.get('id') != 1:
            flash('管理者権限が必要です / Admin access required')
            abort(403)

    # 3. Check for Live2D file access
    if '/static/live2d/' in request.path and not is_localhost:
        user_agent = request.headers.get('User-Agent', '')

        # Additional stricter rate limit for Live2D files: 10 per minute
        is_allowed, retry_after = check_rate_limit(f"{ip_address}:live2d", max_requests=10, time_window=60)
        if not is_allowed:
            log_suspicious_activity(ip_address, 'LIVE2D_RATE_LIMIT', request.path)
            response = make_response('Too Many Requests', 429)
            response.headers['Retry-After'] = str(retry_after)
            return response

        # Block suspicious user agents
        if is_suspicious_user_agent(user_agent):
            log_suspicious_activity(ip_address, 'SUSPICIOUS_USER_AGENT', user_agent)
            abort(403)

        # Block direct file downloads for protected models
        protected_models = ['VTuber_Michelle', 'AmamizuAi_VTuber']
        for model in protected_models:
            if model in request.path:
                # Only allow requests with proper referer from same domain
                referer = request.headers.get('Referer', '')
                if not referer or request.host not in referer:
                    log_suspicious_activity(ip_address, 'INVALID_REFERER',
                                          f'{request.path} - Referer: {referer}')
                    abort(403)

                # Require AJAX header for critical model files
                if any(ext in request.path for ext in ['.moc3', '.model3.json', '.png', '.physics3.json']):
                    if not request.headers.get('X-Requested-With'):
                        log_suspicious_activity(ip_address, 'DIRECT_FILE_ACCESS', request.path)
                        abort(403)

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # For Live2D files, add strict cache control
    if '/static/live2d/' in request.path:
        # Prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        # Add CORS for same-origin only
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'

    # General security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

    # Prevent search engine indexing of Live2D files
    if '/static/live2d/' in request.path:
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'

    return response

# Protected route decorator for admin functions
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('認証が必要です / Authentication required')
            return redirect(url_for('login.login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin route to view suspicious activity (protected)
@app.route('/admin/security-log')
def security_log():
    """View recent suspicious activity - Admin only"""
    # Check if user is logged in
    if 'username' not in session:
        flash('ログインが必要です / Login required')
        return redirect(url_for('login.login'))

    # Check if user is admin (user ID 1)
    if session.get('id') != 1:
        flash('管理者権限が必要です / Admin access required')
        abort(403)

    return render_template('security_log.html',
                         title='Security Log',
                         logs=suspicious_activity_log[-100:],  # Last 100 entries
                         userid=session.get('id'))

# ================== End Security Protection Layer ==================

@app.route('/')
def index():

    con = get_db()
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, password NOT NULL)"
    )
    con.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, userid INTEGER NOT NULL, username TEXT NOT NULL, title TEXT, post NOT NULL, like INTEGER DEFAULT 0)"
        )
    con.execute("CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY AUTOINCREMENT, postid INTEGER DEFAULT 0, userid INTEGER, likecheck INTEGER DEFAULT 0)"
        )
    con.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, postid INTEGER DEFAULT 0, userid INTEGER, tagname TEXT NOT NULL, tagcheck INTEGER DEFAULT 0)"
        )
    optiondb()

    c = con.cursor()
    c.execute("SELECT MAX(postid) AS maxpostid FROM likes")
    maxlikes = c.fetchone()
    maxlike = maxlikes[0]

    c = con.cursor()
    c.execute("SELECT MAX(id) FROM posts")
    max = c.fetchone()
    maxpost = max[0]

    if maxpost == None and maxlike is None:
        gap = 0
        maxpost = 0
        maxlike = 0

    elif maxpost == 1 and maxlike is None:
        gap = 1
        maxpost = 1
        maxlike = 0

    else:
           gap = maxpost - maxlike

    c = con.cursor()
    c.execute("SELECT id FROM posts LIMIT ? OFFSET ?", (gap,maxlike,))
    cur = c.fetchall()


    for row in cur:

        newpostid = row[0]
        userid=0
        likecheck=0

        c.execute(
            "INSERT INTO likes (postid, userid, likecheck) VALUES (?, ?, ?)",
            [newpostid,userid,likecheck]
            )
        con.commit()


    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'option' OR categories = 'planTitle'  ORDER BY orders")
    options = cur.fetchall()

    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'plan' ORDER BY orders")
    plans = cur.fetchall()

    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'planTitle' ORDER BY orders")
    planTitles = cur.fetchall()

    # Get stream schedule before UpdatePosts closes the connection
    c = con.cursor()
    c.execute("SELECT * FROM stream_schedule ORDER BY CASE day_of_week WHEN 'Sunday' THEN 0 WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 END")
    schedules_raw = c.fetchall()

    # Convert CEST to multiple timezones with dates
    schedules = []
    for schedule in schedules_raw:
        schedule_list = list(schedule)
        if schedule_list[4]:  # If time exists
            try:
                # Parse CEST time
                cest_time = datetime.strptime(schedule_list[4], '%H:%M')

                # Calculate EST (CEST - 7 hours) and JST (CEST + 7 hours)
                est_time = cest_time - timedelta(hours=7)
                jst_time = cest_time + timedelta(hours=7)

                # Get current date for reference
                today = datetime.now()
                base_date = today.replace(hour=cest_time.hour, minute=cest_time.minute)
                est_date = base_date - timedelta(hours=7)
                jst_date = base_date + timedelta(hours=7)

                # Format: "Month Day, Year HH:MM TIMEZONE"
                est_str = est_date.strftime('%B %d, %Y') + ' ' + est_time.strftime('%H:%M') + ' EST'
                jst_str = jst_date.strftime('%B %d, %Y') + ' ' + jst_time.strftime('%H:%M') + ' JST'
                cest_str = base_date.strftime('%B %d, %Y') + ' ' + cest_time.strftime('%H:%M') + ' CEST'

                # Store all three timezones in order: JST, CEST, EST
                schedule_list[4] = f"{jst_str}|||{cest_str}|||{est_str}"
            except:
                schedule_list[4] = schedule_list[4]
        schedules.append(tuple(schedule_list))

    if 'username' in session:
        userid = session['id']
    else:
        userid = 0

    Posts1 = UpdatePosts(userid = userid, countend = 0, seetags = '')
    Posts1.Posts()

    posts = Posts1.posts
    tags = Posts1.tags
    tagbox = Posts1.tagbox
    count = Posts1.count

    return render_template('home.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/HOME】', posts = posts, userid = userid, tags= tags, \
                            tagbox = tagbox, count = count, options = options, planTitles = planTitles, plans = plans, schedules = schedules)


@app.route('/newcontents', methods=['POST'])
def newcontents():
    contents = request.form['contents']
    countend = int(contents)

    if 'username' in session:
        userid = session['id']
    else:
        userid = 0


    Posts = UpdatePosts(userid = userid, countend = countend, seetags = '')
    Posts.Posts()

    posts = Posts.posts
    tags = Posts.tags
    tagbox = Posts.tagbox
    count = Posts.count

    return render_template('newcontents.html', title = 'Live2DTree home', posts = posts, userid = userid, tags = tags, tagbox = tagbox, count = count )



@app.route('/about')
def about():
    return render_template('about.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/About】')

@app.route('/reply')
def reply():
    return render_template('reply.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Reply】')

@app.route('/editnintahp')
def editnintahp():
    return render_template('editpage.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Edit】')

@app.route('/editnintahpsend', methods=['POST'])
def editnintahpsend():
    name = request.form['name']
    content = request.form['content']

    con = get_db()
    con.execute(
            "INSERT INTO contents (name, content) VALUES (?, ?)",
            [name, content]
        )
    con.commit()
    con.close()

    return redirect(url_for('home'))

@app.route('/editnintahpedit', methods=['POST'])
def editnintahpedit():
    id = request.form['id']
    name = request.form['name']
    content = request.form['content']

    con = get_db()
    con.execute("UPDATE contents SET content = (?) WHERE id = (?)",
                [content,id]
                )
    con.commit()
    con.close()
    return redirect(url_for('home'))

@app.route('/schedule')
def schedule():
    from datetime import datetime, timedelta

    con = get_db()
    c = con.cursor()
    c.execute("SELECT * FROM stream_schedule ORDER BY CASE day_of_week WHEN 'Sunday' THEN 0 WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 END")
    schedules_raw = c.fetchall()

    # Get last updated timestamp
    c.execute("SELECT MAX(updated_at) FROM stream_schedule")
    last_updated = c.fetchone()[0]
    con.close()

    # Convert CEST to multiple timezones with dates
    schedules = []
    for schedule in schedules_raw:
        schedule_list = list(schedule)
        if schedule_list[4]:  # If time exists
            try:
                # Parse CEST time
                cest_time = datetime.strptime(schedule_list[4], '%H:%M')

                # Calculate EST (CEST - 7 hours) and JST (CEST + 7 hours)
                est_time = cest_time - timedelta(hours=7)
                jst_time = cest_time + timedelta(hours=7)

                # Get current date for reference
                today = datetime.now()
                base_date = today.replace(hour=cest_time.hour, minute=cest_time.minute)
                est_date = base_date - timedelta(hours=7)
                jst_date = base_date + timedelta(hours=7)

                # Format: "Month Day, Year HH:MM TIMEZONE"
                est_str = est_date.strftime('%B %d, %Y') + ' ' + est_time.strftime('%H:%M') + ' EST'
                jst_str = jst_date.strftime('%B %d, %Y') + ' ' + jst_time.strftime('%H:%M') + ' JST'
                cest_str = base_date.strftime('%B %d, %Y') + ' ' + cest_time.strftime('%H:%M') + ' CEST'

                # Store all three timezones in order: JST, CEST, EST
                schedule_list[4] = f"{jst_str}|||{cest_str}|||{est_str}"
            except:
                schedule_list[4] = schedule_list[4]
        schedules.append(tuple(schedule_list))

    # Create timestamp from last_updated or current time
    if last_updated:
        try:
            timestamp = int(datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S').timestamp())
        except:
            timestamp = int(time.time())
    else:
        timestamp = int(time.time())

    return render_template('schedule_page.html', title='配信予定 / Streaming Schedule', schedules=schedules, timestamp=timestamp)

@app.route('/schedule_image.png')
def schedule_image():
    from PIL import Image, ImageDraw, ImageFont
    from datetime import datetime, timedelta
    import io

    try:
        # Get timestamp parameter for cache busting
        timestamp = request.args.get('t', '')

        # Check if we have a cached image that's still valid
        static_path = os.path.join('static', 'schedule_image.png')
        if os.path.exists(static_path) and timestamp:
            # Return cached image
            return send_file(static_path, mimetype='image/png',
                           max_age=0,  # Don't cache in browser
                           cache_timeout=0,
                           conditional=False,
                           etag=False,
                           last_modified=None)
        # Get schedule data
        con = get_db()
        c = con.cursor()
        c.execute("SELECT * FROM stream_schedule ORDER BY CASE day_of_week WHEN 'Sunday' THEN 0 WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 END")
        schedules_raw = c.fetchall()
        con.close()

        # Convert CEST to multiple timezones with dates
        schedules = []
        for schedule in schedules_raw:
            schedule_list = list(schedule)
            if schedule_list[4]:  # If time exists
                try:
                    # Parse CEST time
                    cest_time = datetime.strptime(schedule_list[4], '%H:%M')

                    # Calculate EST (CEST - 7 hours) and JST (CEST + 7 hours)
                    est_time = cest_time - timedelta(hours=7)
                    jst_time = cest_time + timedelta(hours=7)

                    # Get current date for reference
                    today = datetime.now()
                    base_date = today.replace(hour=cest_time.hour, minute=cest_time.minute)
                    est_date = base_date - timedelta(hours=7)
                    jst_date = base_date + timedelta(hours=7)

                    # Format: "Month Day, Year HH:MM"
                    est_str = est_date.strftime('%b %d, %Y %H:%M EST')
                    jst_str = jst_date.strftime('%b %d, %Y %H:%M JST')
                    cest_str = base_date.strftime('%b %d, %Y %H:%M CEST')

                    # Store all three timezones
                    schedule_list[4] = (jst_str, cest_str, est_str)
                except:
                    schedule_list[4] = None
            schedules.append(tuple(schedule_list))
        schedules = tuple(schedules)

        # Create larger image to fit 3 timezones and 7 days
        width = 1400
        height = 1400
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Try to use a Japanese-compatible font, fallback to default - Larger sizes
        font_paths = [
            # Linux/Server fonts
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
            "/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # Windows fonts (for local development)
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
        ]

        title_font = None
        header_font = None
        content_font = None

        for font_path in font_paths:
            try:
                title_font = ImageFont.truetype(font_path, 60)
                header_font = ImageFont.truetype(font_path, 40)
                content_font = ImageFont.truetype(font_path, 36)
                break
            except:
                continue

        # If no font found, use default
        if not title_font:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            content_font = ImageFont.load_default()

        # Draw gradient background (top section) - Pastel colors
        for i in range(150):
            r = int(184 + (201 - 184) * i / 150)
            g = int(201 + (179 - 201) * i / 150)
            b = int(245 + (224 - 245) * i / 150)
            draw.rectangle([(0, i), (width, i+1)], fill=(r, g, b))

        # Add favicon icon to title
        try:
            import os
            favicon_path = os.path.join('static', 'images', 'favicon_VTube.png')
            favicon = Image.open(favicon_path)
            favicon_size = 48
            favicon_resized = favicon.resize((favicon_size, favicon_size), Image.LANCZOS)
        except:
            favicon_resized = None

        # Draw title with icon
        title = "配信予定 / Streaming Schedule"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]

        # Calculate positions for icon and text
        total_width = favicon_size + 20 + title_width if favicon_resized else title_width
        start_x = (width - total_width) / 2

        # Draw icon if available
        if favicon_resized:
            icon_y = 40
            if favicon_resized.mode == 'RGBA':
                img.paste(favicon_resized, (int(start_x), icon_y), favicon_resized)
            else:
                img.paste(favicon_resized, (int(start_x), icon_y))
            text_x = start_x + favicon_size + 20
        else:
            text_x = start_x

        draw.text((text_x, 40), title, fill='white', font=title_font)

        # Draw table with larger rows for 3 timezones
        start_y = 180
        row_height = 150  # Increased for 3 lines of time
        col_widths = [250, 600, 550]

        # Draw header - Pastel colors
        headers = ['曜日 / Day', '時間 / Time', '配信タイトル / Title']
        x = 0
        for i, header in enumerate(headers):
            draw.rectangle([(x, start_y), (x + col_widths[i], start_y + 80)],
                          fill=(184, 201, 245))
            header_bbox = draw.textbbox((0, 0), header, font=header_font)
            header_width = header_bbox[2] - header_bbox[0]
            draw.text((x + (col_widths[i] - header_width) / 2, start_y + 25),
                     header, fill=(74, 74, 74), font=header_font)
            x += col_widths[i]

        # Draw schedule rows
        day_labels = {
            'Sunday': '日 / Sun',
            'Monday': '月 / Mon',
            'Tuesday': '火 / Tue',
            'Wednesday': '水 / Wed',
            'Thursday': '木 / Thu',
            'Friday': '金 / Fri',
            'Saturday': '土 / Sat'
        }

        # Use the same font logic for small_font
        small_font = None
        for font_path in font_paths:
            try:
                small_font = ImageFont.truetype(font_path, 28)
                break
            except:
                continue

        if not small_font:
            small_font = ImageFont.load_default()

        y = start_y + 80
        for schedule in schedules:
            day = day_labels.get(schedule[1], schedule[1])
            times = schedule[4] if schedule[4] else None
            title_text = schedule[5] if schedule[5] else '未定 / TBD'

            # Draw row background
            draw.rectangle([(0, y), (width, y + row_height)],
                          outline=(224, 224, 224), width=2)

            # Draw day - Pastel color
            draw.text((20, y + 60), day, fill=(143, 163, 232), font=content_font)

            # Draw times (3 timezones vertically) - Darker colors for visibility
            if times and isinstance(times, tuple) and len(times) == 3:
                draw.text((270, y + 15), f"JST: {times[0]}", fill=(200, 40, 60), font=small_font)
                draw.text((270, y + 55), f"CEST: {times[1]}", fill=(80, 110, 200), font=small_font)
                draw.text((270, y + 95), f"EST: {times[2]}", fill=(30, 140, 60), font=small_font)
            else:
                draw.text((270, y + 60), '未定 / TBD', fill=(153, 153, 153), font=content_font)

            # Draw title
            draw.text((890, y + 60), title_text, fill=(51, 51, 51), font=content_font)

            y += row_height

        # Add Ninta_Dadcat1 image as semi-transparent watermark behind the table
        try:
            import os
            from PIL import ImageEnhance
            dadcat_path = os.path.join('static', 'images', 'Ninta_Dadcat1.png')
            dadcat_img = Image.open(dadcat_path)

            # Convert to RGBA if not already
            if dadcat_img.mode != 'RGBA':
                dadcat_img = dadcat_img.convert('RGBA')

            # Resize to large size (about 600px width)
            dadcat_width = 600
            dadcat_ratio = dadcat_width / dadcat_img.width
            dadcat_resized = dadcat_img.resize((dadcat_width, int(dadcat_img.height * dadcat_ratio)), Image.LANCZOS)

            # Create a new image for the watermark with lower opacity (20% opacity)
            watermark = Image.new('RGBA', img.size, (255, 255, 255, 0))

            # Position in center-right of the table area
            dadcat_x = width - dadcat_width - 50
            dadcat_y = 350

            # Adjust alpha channel for transparency
            alpha = dadcat_resized.split()[3]
            alpha = alpha.point(lambda p: int(p * 0.2))  # 20% opacity
            dadcat_resized.putalpha(alpha)

            # Paste on watermark layer
            watermark.paste(dadcat_resized, (dadcat_x, dadcat_y), dadcat_resized)

            # Composite the watermark onto the main image
            img = Image.alpha_composite(img.convert('RGBA'), watermark).convert('RGB')
            draw = ImageDraw.Draw(img)
        except Exception as dadcat_error:
            import sys
            sys.stderr.write(f"Warning: Could not add Dadcat watermark: {str(dadcat_error)}\n")

        # Draw footer
        footer_text = "Ninta Live2D & Art | @ninta_mk3"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=content_font)
        footer_width = footer_bbox[2] - footer_bbox[0]
        draw.text(((width - footer_width) / 2, height - 60),
                 footer_text, fill=(102, 102, 102), font=content_font)

        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        # Also save to static file for easier serving
        try:
            import os
            static_path = os.path.join('static', 'schedule_image.png')
            img.save(static_path, 'PNG')
        except Exception as save_error:
            import sys
            sys.stderr.write(f"Warning: Could not save static image: {str(save_error)}\n")

        # Create response with no-cache headers
        response = make_response(send_file(img_io, mimetype='image/png'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    except Exception as e:
        import sys
        sys.stderr.write(f"Error generating schedule image: {str(e)}\n")
        abort(500)

@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    import sys
    try:
        # Check if user is logged in
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Login required'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400

        con = get_db()
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

        for day in days:
            day_data = data.get(day, {})
            stream_time = day_data.get('time', '')
            stream_title = day_data.get('title', '')
            con.execute(
                "UPDATE stream_schedule SET stream_time = ?, stream_title = ?, updated_at = CURRENT_TIMESTAMP WHERE day_of_week = ?",
                [stream_time, stream_title, day]
            )

        con.commit()
        con.close()

        # Delete cached schedule image to force regeneration
        try:
            static_path = os.path.join('static', 'schedule_image.png')
            if os.path.exists(static_path):
                os.remove(static_path)
        except Exception as cache_error:
            sys.stderr.write(f"Warning: Could not delete cached image: {str(cache_error)}\n")

        return jsonify({'success': True, 'message': 'Schedule updated successfully'})

    except Exception as e:
        sys.stderr.write(f"Error updating schedule: {str(e)}\n")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/debug/ogp')
def debug_ogp():
    """Debug endpoint to test OGP meta tags"""
    from datetime import datetime

    con = get_db()
    c = con.cursor()
    c.execute("SELECT MAX(updated_at) FROM stream_schedule")
    last_updated = c.fetchone()[0]
    con.close()

    # Create timestamp
    if last_updated:
        try:
            timestamp = int(datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S').timestamp())
        except:
            timestamp = int(time.time())
    else:
        timestamp = int(time.time())

    ogp_data = {
        'page_url': f"{request.host_url}schedule",
        'image_url': f"{request.host_url}schedule_image.png?t={timestamp}",
        'timestamp': timestamp,
        'last_updated': last_updated,
        'meta_tags': {
            'og:title': 'Ninta配信予定 / Streaming Schedule',
            'og:description': 'JST, CEST, EST - 週間配信予定表 / Weekly Streaming Schedule',
            'og:image': f"{request.host_url}schedule_image.png?t={timestamp}",
            'og:url': f"{request.host_url}schedule",
            'twitter:card': 'summary_large_image',
            'twitter:image': f"{request.host_url}schedule_image.png?t={timestamp}"
        }
    }

    return jsonify(ogp_data)


if __name__ == '__main__':
    app.run(debug=True)
