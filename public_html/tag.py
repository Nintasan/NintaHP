import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session, flash, current_app
from flask import Blueprint
from db import UpdatePosts
from db import get_db



bp_tag = Blueprint('tag', __name__)

@bp_tag.route('/selecttag', methods=['POST'])
def selecttag():
    seetags = request.form['tags']
    

    if 'username' in session:
        userid = session['id']
    else:
        userid = 0

    Posts1 = UpdatePosts(userid = userid, countend = 0, seetags = seetags)
    Posts1.Posts()

    posts = Posts1.posts
    tags = Posts1.tags
    tagbox = Posts1.tagbox
    count = Posts1.count
    seetags = Posts1.seetags

    return render_template('seetags.html', title = 'Live2DTree home', posts = posts, userid = userid, tags = tags, count = count, seetags = seetags, tagbox = tagbox)


@bp_tag.route('/tagnewcontents', methods=['POST'])
def tagnewcontents():
    seetags = request.form['seetags']
    contents = request.form['contents']

    countend = int(contents)

    

    if 'username' in session:
        userid = session['id']
    else:
        userid = 0
    Posts1 = UpdatePosts(userid = userid, countend = countend, seetags = seetags)
    Posts1.Posts()

    posts = Posts1.posts
    tags = Posts1.tags
    tagbox = Posts1.tagbox
    count = Posts1.count
    seetags = Posts1.seetags
    return render_template('tagnewcontents.html', title = 'Live2DTree home', posts = posts, userid = userid, tags = tags, count = count, seetags = seetags, tagbox = tagbox)



@bp_tag.route('/createtag', methods=['POST'])
def createtag():
        newtag = request.form['newtag']
        userid = session['id']

        con = get_db()
        c = con.cursor()
        c.execute("SELECT * FROM tags WHERE tagname = ? ", (newtag,))
        firsttag = c.fetchone()

        if firsttag is None:

                c.execute(
                        "INSERT INTO tags (userid, tagname) VALUES (?, ?)",
                        [userid, newtag]
                )
                con.commit()
                flash("Success")
        
        else:
                flash("This tag already exists")

        con.close

        return redirect(url_for('index'))

