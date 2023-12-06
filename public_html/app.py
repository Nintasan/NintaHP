import sqlite3
import json
from flask import Flask , render_template , request , g , redirect , url_for , session , flash, current_app
from datetime import timedelta
from signup import bp_signup
from login import bp_login
from tag import bp_tag
from userpage import bp_userpage
from db import bp_db
from db import UpdatePosts
from db import get_db
from db import optiondb
from option import bp_option


app = Flask(__name__)
app.register_blueprint(bp_signup)
app.register_blueprint(bp_login)
app.register_blueprint(bp_tag)
app.register_blueprint(bp_userpage)
app.register_blueprint(bp_db)
app.register_blueprint(bp_option)



app.secret_key = "aaa"
app.permanent_session_lifetime = timedelta(minutes=120)

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

    return render_template('home.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/HOME】', posts = posts, userid = userid, tags= tags, tagbox = tagbox, count = count)
        

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
    con = get_db()
    c = con.cursor()
    cur = c.execute("select * from options ORDER BY id")
    options = cur.fetchall()
    con.close()
    return render_template('contact.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Contact】', options = options)

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
