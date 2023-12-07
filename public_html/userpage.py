import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
import random
import json
from db import UpdatePosts
from db import get_db

bp_userpage = Blueprint('userpage', __name__)

class PostsSabmission:
    def __init__(self, userid, username, title1, postEdit):
           self.userid = userid
           self.username = username
           self.title1 = title1
           self.postEdit = postEdit

    def SendPostsDB(self):
            con = get_db()
            con.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, userid INTEGER NOT NULL, username TEXT NOT NULL, title TEXT, post NOT NULL, like INTEGER DEFAULT 0)"
                )
            con.execute(
                        "INSERT INTO posts (userid, username, title, post) VALUES (?, ?, ?, ?)",
                        [self.userid, self.username, self.title1, self.postEdit]
                    )
            con.commit()
            con.close()
        
@bp_userpage.route('/submission', methods=['POST'])
def submission():
    userid = session['id']
    username = session['username']
    title1 = request.form['title']
    post1 = request.form['post']

    if 'twitter.com' in post1 or 'x.com' in post1:

        postEdit = post1.replace("x.com", "twitter.com", 1)

        PostsSabmissionX = PostsSabmission(userid = userid, username = username, title1 = title1, postEdit = postEdit)
        PostsSabmissionX.SendPostsDB()
        return redirect(url_for('index'))



    elif 'www.youtube.com/' in post1 or 'youtube.com/shorts/' in post1 or 'youtu.be/' in post1:

        if 'www.youtube.com/' in post1:

            postEdit = post1.replace("www.youtube.com/watch?v=", "www.youtube.com/embed/", 1)
        
        elif 'youtube.com/shorts/' in post1:

            postEdit = post1.replace("youtube.com/shorts/", "www.youtube.com/embed/", 1)

        else:

            postEdit = post1.replace("youtu.be/", "www.youtube.com/embed/", 1)
            
        

        PostsSabmissionYT = PostsSabmission(userid = userid, username = username, title1 = title1, postEdit = postEdit)
        PostsSabmissionYT.SendPostsDB()
        return redirect(url_for('index'))

    else:
        return redirect(url_for('index'))

@bp_userpage.route('/deletepost', methods=['POST'])
def deletepost():
    postid = request.form['id']
    con = get_db()
    con.execute(
    "DELETE FROM posts WHERE id = ?",
        [postid]
        )
    con.commit()
    con.close()
    
    return redirect(url_for('index'))


class LikesSubmission:
    def __init__(self, id, likeint, likecheck):
        self.id = id
        self.likeint = likeint
        self.likecheck = likecheck
        self.userid = 0
        self.likecount = 0
        self.postlikes = 0
    
    def SendlikesDB(self):
        con = get_db()
        c = con.cursor()
        c.execute("SELECT * FROM posts WHERE id = ? ", (self.id,))
        like =c.fetchone()
        self.likecount = like[5] + self.likeint 

        con.execute("UPDATE posts SET like = (?) WHERE id = (?)",
                    [self.likecount, self.id]
                    )
        con.commit()

        self.userid = session['id']
    
    def UpdateLikes(self):
        self.userid = session['id']
        con = get_db()
        con.execute("UPDATE likes SET likecheck = (?) WHERE postid = (?) AND userid = (?)",
                [self.likecheck, self.id, self.userid]
                )
        con.commit()

        c = con.cursor()
        c.execute("SELECT * FROM posts WHERE id = ? ", (self.id,))
        self.postlikes =c.fetchone()
        con.close

@bp_userpage.route('/likes', methods=['POST'])
def likes():
    id = request.form['id']

    LikesSubmissionLike = LikesSubmission(id = id, likeint = 1, likecheck = 1)
    LikesSubmissionLike.SendlikesDB()

    userid = LikesSubmissionLike.userid
    likecheck = LikesSubmissionLike.likecheck

    con = get_db()
    c = con.cursor()
    c.execute("SELECT * FROM likes WHERE postid = ? AND userid = ? ", (id, userid))
    firstlike = c.fetchone()
    con.close

    if firstlike is None:
        con =get_db()
        con.execute(
                "INSERT INTO likes (postid, userid, likecheck) VALUES (?, ?, ?)",
                [id, userid, likecheck]
            )
        con.commit()
 
        c = con.cursor()
        c.execute("SELECT * FROM posts WHERE id = ? ", (id,))
        postunlikes =c.fetchone()
        con.close

        return render_template('unlikes.html', postunlikes=postunlikes)

    else:
        UpdateUnlike = LikesSubmission(id = id, likeint = 1, likecheck = 1)
        UpdateUnlike.UpdateLikes()

        postunlikes = UpdateUnlike.postlikes
    return render_template('unlikes.html', postunlikes=postunlikes)

@bp_userpage.route('/unlikes', methods=['POST'])
def unlikes():

    id = request.form['id']

    LikesSubmissionUnlike = LikesSubmission(id = id, likeint = -1, likecheck = 0)
    LikesSubmissionUnlike.SendlikesDB()

    userid = LikesSubmissionUnlike.userid
    likecheck = LikesSubmissionUnlike.likecheck

    UpdateUnlike = LikesSubmission(id = id, likeint = -1, likecheck = 0)
    UpdateUnlike.UpdateLikes()

    postlikes = UpdateUnlike.postlikes

    return render_template('likes.html', postlikes=postlikes)


@bp_userpage.route('/tags', methods=['POST'])
def tags():
    tagname = request.form['tag']
    postid0 = request.form['postid']
    userid = session['id']
    tagcheck = 1

    con = get_db()
    c = con.cursor()
    c.execute("SELECT * FROM tags WHERE postid = ? AND userid = ? AND tagname = ? ", (postid0, userid, tagname))
    firsttag = c.fetchone()

    if firsttag is None:
        c.execute(
                "INSERT INTO tags (postid, userid, tagname, tagcheck) VALUES (?, ?, ?, ?)",
                [postid0, userid, tagname, tagcheck]
            )
        con.commit()
    
    
    c.execute("SELECT * FROM tags GROUP BY tagname ORDER BY id DESC"
                    )
    tags = c.fetchall()

    c.execute("SELECT * FROM tags WHERE postid = ? ORDER BY id DESC", (postid0,))
    tagbox = c.fetchall()
    con.close()
    return render_template('tags.html', tagbox = tagbox, tags = tags, postid0 = postid0)
