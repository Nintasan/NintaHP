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
                            tagbox = tagbox, count = count, options = options, planTitles = planTitles, plans = plans)


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

@app.route('/contact')
def contact():
    if 'username' in session:
        userid = session['id']
    else:
        userid = 0

    con = get_db()
    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'option' OR categories = 'planTitle'  ORDER BY orders")
    options = cur.fetchall()

    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'plan' ORDER BY orders")
    plans = cur.fetchall()

    c = con.cursor()
    cur = c.execute("select * from options WHERE categories = 'planTitle' ORDER BY orders")
    planTitles = cur.fetchall()
    con.close()

    return render_template('contact.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Contact】', userid = userid, options = options, planTitles = planTitles, plans = plans)

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



if __name__ == '__main__':
    app.run(debug=True)
