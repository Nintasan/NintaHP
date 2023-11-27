import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session , flash, current_app
from datetime import timedelta
from signup import bp_signup
from login import bp_login
from about import bp_about
from contact import bp_contact
from tag import bp_tag


app = Flask(__name__)
app.register_blueprint(bp_signup)
app.register_blueprint(bp_login)
app.register_blueprint(bp_about)
app.register_blueprint(bp_contact)
app.register_blueprint(bp_tag)



app.secret_key = "aaa"
app.permanent_session_lifetime = timedelta(minutes=120)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('ninta.db')
    return g.db

class UpdatePosts:
    def __init__(self, userid, countend, seetags):
           self.userid = userid
           self.countend = countend
           self.seetags = seetags
           self.posts = 0
           self.tags = 0
           self.tagbox = 0
           self.count = 5

    def Posts(self):

                con = get_db()
                c = con.cursor()
                if self.userid == 0:
                    if self.countend == 0 and len(self.seetags) == 0:
                        c.execute("SELECT * FROM posts ORDER BY id DESC LIMIT ?",
                            [self.count]
                            )
                        
                    elif len(self.seetags) == 0:
                        c.execute("SELECT * FROM posts ORDER BY id DESC LIMIT (?) OFFSET (?) ",
                            [self.count, self.countend]
                            )
                        
                    elif self.countend == 0:
                        c.execute("SELECT DISTINCT posts.id, posts.userid, posts.username, posts.title, posts.post, posts.like, tags.tagname  \
                        FROM tags \
                              LEFT JOIN posts ON tags.postid = posts.id \
                              WHERE tags.tagname = ? AND tags.tagcheck = 1 != 0\
                              GROUP BY posts.id \
                              ORDER BY posts.id DESC\
                               LIMIT 5",
                              [self.seetags]
                              )
                    
                    else:
                         c.execute("SELECT DISTINCT posts.id, posts.userid, posts.username, posts.title, posts.post, posts.like, tags.tagname \
                              FROM tags \
                              LEFT JOIN posts ON tags.postid = posts.id \
                              WHERE tags.tagcheck = 1 AND tags.tagname = ? \
                              GROUP BY posts.id \
                              ORDER BY posts.id DESC \
                              LIMIT ? OFFSET ?",
                              [self.seetags, self.count, self.countend]
                              )

                else:
                    if self.countend == 0 and len(self.seetags) == 0:  
                        c.execute("SELECT DISTINCT ifnull(posts.id,0), posts.userid, posts.username, posts.title, posts.post, ifnull(posts.like,0), ifnull(likes.postid,0), \
                            ifnull(likes.likecheck,0), MAX(likes.userid) \
                            FROM posts \
                            LEFT JOIN likes ON posts.id = likes.postid \
                            WHERE likes.userid = 0 OR likes.userid = ? GROUP BY posts.id \
                            ORDER BY posts.id DESC LIMIT ? " ,
                            [self.userid, self.count]
                            )
                        
                    elif len(self.seetags) == 0:
                        c.execute("SELECT DISTINCT ifnull(posts.id,0), posts.userid, posts.username, posts.title, posts.post, ifnull(posts.like,0), \
                              ifnull(likes.postid,0), ifnull(likes.likecheck,0), MAX(likes.userid) \
                              FROM posts LEFT JOIN likes ON posts.id = likes.postid \
                              WHERE likes.userid = 0 OR likes.userid = ? \
                              GROUP BY posts.id \
                              ORDER BY posts.id DESC LIMIT ? OFFSET ?" ,
                            [self.userid, self.count, self.countend]
                            )
                        
                    elif self.countend == 0:
                        c.execute("SELECT DISTINCT ifnull(posts.id,0), posts.userid, posts.username, posts.title, posts.post, ifnull(posts.like,0), ifnull(likes.postid,0),\
                               ifnull(likes.likecheck,0), MAX(likes.userid), tags.tagname\
                        FROM tags \
                        LEFT JOIN likes ON tags.postid = likes.postid \
                        LEFT JOIN posts ON tags.postid = posts.id \
                        WHERE ( likes.userid = 0 OR likes.userid = ? ) AND tags.tagname = ? \
                        GROUP BY posts.id \
                        ORDER BY posts.id DESC \
                        LIMIT 5" ,
                        [self.userid, self.seetags]
                            )
                         
                    else:
                        c.execute("SELECT DISTINCT ifnull(posts.id,0), posts.userid, posts.username, posts.title, posts.post, ifnull(posts.like,0), ifnull(likes.postid,0),\
                               ifnull(likes.likecheck,0), MAX(likes.userid), tags.tagname\
                        FROM tags \
                        LEFT JOIN likes ON tags.postid = likes.postid \
                        LEFT JOIN posts ON tags.postid = posts.id \
                        WHERE ( likes.userid = 0 OR likes.userid = ? ) AND tags.tagname = ? AND tags.tagcheck = 1\
                        GROUP BY posts.id \
                        ORDER BY posts.id DESC \
                              LIMIT ? OFFSET ?" ,
                            [self.userid, self.seetags, self.count, self.countend]
                            )
           
                self.posts = c.fetchall()

                c.execute("SELECT * FROM tags GROUP BY tagname ORDER BY id DESC"
                            )
                self.tags = c.fetchall()
                c.execute("SELECT * FROM tags ORDER BY id DESC"
                            )
                self.tagbox = c.fetchall()
                con.close()
                self.count = self.countend + self.count
                



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

    return render_template('home.html', title = 'Live2DTree home', posts = posts, userid = userid, tags= tags, tagbox = tagbox, count = count)
        

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
    return g.db


@app.route('/')
def home():
    con = get_db()
    con.execute("CREATE TABLE IF NOT EXISTS contents (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, content NOT NULL)"
        )
    c = con.cursor()
    cur = c.execute("select * from contents ORDER BY id")
    content = cur.fetchall()
    con.close()
    return render_template('home.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/HOME】', content = content)

@app.route('/about')
def about():
    return render_template('about.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/About】')

@app.route('/contact')
def contact():
    con = get_db()
    con.execute("CREATE TABLE IF NOT EXISTS contents (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, content NOT NULL)"
        )
    c = con.cursor()
    cur = c.execute("select * from contents ORDER BY id")
    content = cur.fetchall()
    con.close()
    return render_template('contact.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Contact】', content = content)

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
