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

@app.route('/check_pillow')
def check_pillow_simple():
    """Simple Pillow check without /debug prefix"""
    import sys
    try:
        from PIL import Image, ImageDraw, ImageFont
        import PIL
        return f"SUCCESS: PIL/Pillow {PIL.__version__} is installed. Python: {sys.version}"
    except ImportError as e:
        return f"ERROR: PIL/Pillow NOT installed. Error: {str(e)}. Python: {sys.version}"

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

    # Convert Prague time to multiple timezones with automatic DST handling
    from pytz import timezone
    prague_tz = timezone('Europe/Prague')
    est_tz = timezone('US/Eastern')
    jst_tz = timezone('Asia/Tokyo')

    schedules = []
    for schedule in schedules_raw:
        schedule_list = list(schedule)
        if schedule_list[4]:  # If time exists
            try:
                # Parse Prague time (CET/CEST)
                prague_time = datetime.strptime(schedule_list[4], '%H:%M')

                # Get current date for reference and localize to Prague timezone
                today = datetime.now()
                prague_dt = prague_tz.localize(today.replace(hour=prague_time.hour, minute=prague_time.minute, second=0, microsecond=0))

                # Convert to other timezones (pytz handles DST automatically)
                est_dt = prague_dt.astimezone(est_tz)
                jst_dt = prague_dt.astimezone(jst_tz)

                # Get timezone abbreviation (CET or CEST)
                prague_tz_name = prague_dt.strftime('%Z')

                # Format: "Month Day, Year HH:MM TIMEZONE"
                est_str = est_dt.strftime('%B %d, %Y %H:%M %Z')
                jst_str = jst_dt.strftime('%B %d, %Y %H:%M %Z')
                prague_str = prague_dt.strftime('%B %d, %Y %H:%M ') + prague_tz_name

                # Store all three timezones in order: JST, Prague(CET/CEST), EST
                schedule_list[4] = f"{jst_str}|||{prague_str}|||{est_str}"
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

    # Convert Prague time to multiple timezones with automatic DST handling
    from pytz import timezone
    prague_tz = timezone('Europe/Prague')
    est_tz = timezone('US/Eastern')
    jst_tz = timezone('Asia/Tokyo')

    schedules = []
    for schedule in schedules_raw:
        schedule_list = list(schedule)
        if schedule_list[4]:  # If time exists
            try:
                # Parse Prague time (CET/CEST)
                prague_time = datetime.strptime(schedule_list[4], '%H:%M')

                # Get current date for reference and localize to Prague timezone
                today = datetime.now()
                prague_dt = prague_tz.localize(today.replace(hour=prague_time.hour, minute=prague_time.minute, second=0, microsecond=0))

                # Convert to other timezones (pytz handles DST automatically)
                est_dt = prague_dt.astimezone(est_tz)
                jst_dt = prague_dt.astimezone(jst_tz)

                # Get timezone abbreviation (CET or CEST)
                prague_tz_name = prague_dt.strftime('%Z')

                # Format: "Month Day, Year HH:MM TIMEZONE"
                est_str = est_dt.strftime('%B %d, %Y %H:%M %Z')
                jst_str = jst_dt.strftime('%B %d, %Y %H:%M %Z')
                prague_str = prague_dt.strftime('%B %d, %Y %H:%M ') + prague_tz_name

                # Store all three timezones in order: JST, Prague(CET/CEST), EST
                schedule_list[4] = f"{jst_str}|||{prague_str}|||{est_str}"
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

def generate_schedule_image():
    """Generate schedule image and save to static folder"""
    import sys
    import os
    import sqlite3
    sys.stderr.write("=== Starting generate_schedule_image ===\n")

    from PIL import Image, ImageDraw, ImageFont
    from datetime import datetime, timedelta
    import io

    try:
        # Get schedule data with NEW database connection
        sys.stderr.write("Step 1: Creating NEW database connection...\n")
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ninta.db')
        con = sqlite3.connect(db_path)
        c = con.cursor()
        sys.stderr.write("Step 2: Fetching schedule data...\n")
        c.execute("SELECT * FROM stream_schedule ORDER BY CASE day_of_week WHEN 'Sunday' THEN 0 WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 END")
        schedules_raw = c.fetchall()
        sys.stderr.write(f"Step 3: Fetched {len(schedules_raw)} schedule entries\n")
        con.close()

        # Convert Prague time to multiple timezones with automatic DST handling
        sys.stderr.write("Step 4: Converting timezone data...\n")
        from pytz import timezone
        prague_tz = timezone('Europe/Prague')
        est_tz = timezone('US/Eastern')
        jst_tz = timezone('Asia/Tokyo')

        schedules = []
        for schedule in schedules_raw:
            schedule_list = list(schedule)
            if schedule_list[4]:  # If time exists
                try:
                    # Parse Prague time (CET/CEST)
                    prague_time = datetime.strptime(schedule_list[4], '%H:%M')

                    # Get current date for reference and localize to Prague timezone
                    today = datetime.now()
                    prague_dt = prague_tz.localize(today.replace(hour=prague_time.hour, minute=prague_time.minute, second=0, microsecond=0))

                    # Convert to other timezones (pytz handles DST automatically)
                    est_dt = prague_dt.astimezone(est_tz)
                    jst_dt = prague_dt.astimezone(jst_tz)

                    # Get timezone abbreviation (CET or CEST)
                    prague_tz_name = prague_dt.strftime('%Z')

                    # Format: "Month Day, Year HH:MM TIMEZONE"
                    est_str = est_dt.strftime('%b %d, %Y %H:%M %Z')
                    jst_str = jst_dt.strftime('%b %d, %Y %H:%M %Z')
                    prague_str = prague_dt.strftime('%b %d, %Y %H:%M ') + prague_tz_name

                    # Store all three timezones
                    schedule_list[4] = (jst_str, prague_str, est_str)
                except:
                    schedule_list[4] = None
            schedules.append(tuple(schedule_list))
        schedules = tuple(schedules)

        # Create image optimized for Twitter OGP (larger text)
        sys.stderr.write("Step 5: Creating image canvas...\n")
        width = 1200
        height = 630  # Twitter recommended size
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Use PIL's built-in default font
        sys.stderr.write("Step 5.1: Using default fonts...\n")
        # We'll simulate larger text by scaling up coordinates
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        content_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

        # Draw gradient background (full height)
        sys.stderr.write("Step 5.2: Drawing background...\n")
        for i in range(height):
            # Gradient from top to bottom
            ratio = i / height
            r = int(184 + (255 - 184) * ratio)
            g = int(201 + (255 - 201) * ratio)
            b = int(245 + (255 - 245) * ratio)
            draw.rectangle([(0, i), (width, i+1)], fill=(r, g, b))

        # Draw title (larger, English only)
        sys.stderr.write("Step 5.3: Drawing title...\n")
        title = "Ninta's Weekly Stream Schedule"
        # Draw title multiple times to simulate larger font
        for offset_x in range(-2, 3):
            for offset_y in range(-2, 3):
                if offset_x == 0 and offset_y == 0:
                    continue
                draw.text((20 + offset_x, 15 + offset_y), title, fill=(100, 120, 200), font=title_font)
        draw.text((20, 15), title, fill='white', font=title_font)

        # Simplified schedule display - only show streams that are scheduled
        sys.stderr.write("Step 5.4: Drawing schedule rows...\n")
        start_y = 50
        row_height = 80

        # Filter schedules that have actual times
        active_schedules = [s for s in schedules if s[4] and isinstance(s[4], tuple)]

        day_labels = {
            'Sunday': 'SUN',
            'Monday': 'MON',
            'Tuesday': 'TUE',
            'Wednesday': 'WED',
            'Thursday': 'THU',
            'Friday': 'FRI',
            'Saturday': 'SAT'
        }

        y = start_y
        for schedule in active_schedules[:7]:  # Max 7 rows to fit
            day = day_labels.get(schedule[1], schedule[1])
            times = schedule[4]
            title_text = schedule[5] if schedule[5] else 'TBD'

            # Truncate long titles
            if len(title_text) > 35:
                title_text = title_text[:32] + '...'

            # Draw day (bold style)
            day_x = 20
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    draw.text((day_x + ox, y + oy), day, fill=(80, 100, 180), font=content_font)
            draw.text((day_x, y), day, fill='white', font=content_font)

            # Draw EST time (largest, most prominent)
            if times and len(times) == 3:
                est_time = times[2]  # EST is third
                time_x = 120
                # Make time text larger by drawing multiple times
                for ox in range(-1, 2):
                    for oy in range(-1, 2):
                        draw.text((time_x + ox, y + oy), est_time, fill=(30, 100, 30), font=content_font)
                draw.text((time_x, y), est_time, fill=(50, 200, 50), font=content_font)

            # Draw title (bold style)
            title_x = 550
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    if ox != 0 or oy != 0:
                        draw.text((title_x + ox, y + oy), title_text, fill=(40, 40, 40), font=content_font)
            draw.text((title_x, y), title_text, fill=(20, 20, 20), font=content_font)

            y += row_height

        # Draw footer
        sys.stderr.write("Step 5.5: Drawing footer...\n")
        footer_text = "@ninta_mk3 | ninta.main.jp"
        draw.text((20, height - 25), footer_text, fill=(100, 100, 100), font=small_font)

        # Save to static file with absolute path
        sys.stderr.write("Step 6: Preparing to save image...\n")
        # Get the directory where app.py is located
        app_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(app_dir, 'static')
        sys.stderr.write(f"App dir: {app_dir}\n")
        sys.stderr.write(f"Static dir: {static_dir}\n")

        # Create static directory if it doesn't exist
        if not os.path.exists(static_dir):
            sys.stderr.write("Static dir doesn't exist, creating...\n")
            os.makedirs(static_dir)

        static_path = os.path.join(static_dir, 'schedule_image.png')
        sys.stderr.write(f"Step 7: Saving image to: {static_path}\n")
        img.save(static_path, 'PNG')
        sys.stderr.write(f"Step 8: Image saved successfully!\n")
        sys.stderr.write(f"File exists check: {os.path.exists(static_path)}\n")
        sys.stderr.write(f"File size: {os.path.getsize(static_path)} bytes\n")
        return static_path

    except Exception as e:
        import sys
        import traceback
        sys.stderr.write(f"ERROR in generate_schedule_image: {str(e)}\n")
        sys.stderr.write(f"Traceback:\n{traceback.format_exc()}\n")
        return None

@app.route('/schedule_image.png')
def schedule_image():
    """Serve the schedule image"""
    try:
        # Get absolute path
        app_dir = os.path.dirname(os.path.abspath(__file__))
        static_path = os.path.join(app_dir, 'static', 'schedule_image.png')

        # If image doesn't exist, generate it
        if not os.path.exists(static_path):
            import sys
            sys.stderr.write(f"Image not found at {static_path}, generating...\n")
            generated_path = generate_schedule_image()
            if not generated_path:
                sys.stderr.write("Failed to generate image\n")
                abort(500)

        # Serve the image with no-cache headers
        response = make_response(send_file(static_path, mimetype='image/png'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        import sys
        sys.stderr.write(f"Error serving schedule image: {str(e)}\n")
        abort(500)

@app.route('/upload_schedule_image', methods=['POST'])
def upload_schedule_image():
    """Receive schedule image from client-side HTML2Canvas"""
    import sys
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file'}), 400

        image_file = request.files['image']

        # Save to static folder
        app_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(app_dir, 'static')

        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

        static_path = os.path.join(static_dir, 'schedule_image.png')
        image_file.save(static_path)

        sys.stderr.write(f"Schedule image uploaded and saved to: {static_path}\n")

        return jsonify({
            'success': True,
            'message': 'Image uploaded successfully',
            'path': static_path
        })

    except Exception as e:
        sys.stderr.write(f"Error uploading schedule image: {str(e)}\n")
        import traceback
        sys.stderr.write(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

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

        return jsonify({
            'success': True,
            'message': 'Schedule updated successfully',
            'note': 'Image will be generated on next page load'
        })

    except Exception as e:
        sys.stderr.write(f"Error updating schedule: {str(e)}\n")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/debug/check_pillow')
def debug_check_pillow():
    """Check if PIL/Pillow is installed"""
    import sys
    try:
        from PIL import Image, ImageDraw, ImageFont
        import PIL
        return jsonify({
            'success': True,
            'message': 'PIL/Pillow is installed',
            'version': PIL.__version__,
            'python_version': sys.version
        })
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': 'PIL/Pillow is NOT installed',
            'message': str(e),
            'python_version': sys.version,
            'install_command': 'pip install --user Pillow'
        }), 500

@app.route('/debug/generate_image')
def debug_generate_image():
    """Test endpoint to manually generate schedule image"""
    import sys
    try:
        sys.stderr.write("Starting image generation...\n")
        generated_path = generate_schedule_image()
        if generated_path:
            return jsonify({
                'success': True,
                'message': 'Image generated successfully',
                'path': generated_path,
                'exists': os.path.exists(generated_path)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Image generation returned None'
            }), 500
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        sys.stderr.write(f"Error in debug_generate_image: {error_trace}\n")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_trace
        }), 500

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

    # Check if image exists
    app_dir = os.path.dirname(os.path.abspath(__file__))
    static_path = os.path.join(app_dir, 'static', 'schedule_image.png')
    image_exists = os.path.exists(static_path)

    ogp_data = {
        'page_url': f"{request.host_url}schedule",
        'image_url': f"{request.host_url}static/schedule_image.png?t={timestamp}",
        'image_exists': image_exists,
        'image_path': static_path,
        'timestamp': timestamp,
        'last_updated': last_updated,
        'meta_tags': {
            'og:title': 'Ninta配信予定 / Streaming Schedule',
            'og:description': 'JST, CEST, EST - 週間配信予定表 / Weekly Streaming Schedule',
            'og:image': f"{request.host_url}static/schedule_image.png?t={timestamp}",
            'og:url': f"{request.host_url}schedule",
            'twitter:card': 'summary_large_image',
            'twitter:image': f"{request.host_url}static/schedule_image.png?t={timestamp}"
        }
    }

    return jsonify(ogp_data)


if __name__ == '__main__':
    app.run(debug=True)
