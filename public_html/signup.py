import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash
from db import UpdatePosts
from db import get_db

bp_signup = Blueprint('user', __name__)

@bp_signup.route('/signup')
def signup():
    return render_template('signup.html', title = 'Live2DTree signup')

@bp_signup.route('/register', methods=['POST'])
def register():
        username = request.form['username']
        password = request.form['password']
        
        con = get_db()
        con.execute(
                "INSERT INTO users (USERNAME, PASSWORD) VALUES (?, ?)",
                [username, generate_password_hash(password)]
            )
        con.commit()
        con.close()
        return redirect(url_for('user.signup'))