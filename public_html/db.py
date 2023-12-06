import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash

bp_db = Blueprint('db', __name__)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('ninta.db')
    return g.db

def optiondb():
    con = get_db()
    con.execute("CREATE TABLE IF NOT EXISTS options (id INTEGER PRIMARY KEY AUTOINCREMENT, namejp TEXT NOT NULL, nameen TEXT NOT NULL, pricejp NOT NULL, priceen TEXT NOT NULL)"
        )
    


class UpdatePosts:
    def __init__(self, userid, countend, seetags):
           self.userid = userid
           self.countend = countend
           self.seetags = seetags
           self.posts = 0
           self.tags = 0
           self.tagbox = 0
           self.count = 6

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