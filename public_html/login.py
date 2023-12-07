import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash
from db import UpdatePosts
from db import get_db

bp_login = Blueprint('login', __name__)

@bp_login.route('/login')
def login():
    return render_template('login.html', title = 'NintaHP login')

@bp_login.route('/access', methods=['POST'])
def access():
        username = request.form['username']
        password = request.form['password']
        con = get_db()
        c = con.cursor()
        c.execute(
            "SELECT * FROM users WHERE USERNAME = ?", (username, )
        )
        user = c.fetchone()

        if user is None:
            return redirect(url_for('login.login'))
        
        else:
            passdb = user[2]
            if check_password_hash(passdb, password):
                session['id'] = user[0]
                session['username'] = username
                return redirect(url_for('index'))
            
            else:
                 return redirect(url_for('login.login'))



@bp_login.route('/member')
def member():
    if 'username' in session:
            return render_template('home.html', title = 'Live2DTree userpage')

    else:
        return redirect(url_for('login.login'))




@bp_login.route('/logout')
def log_out():
    session.clear()
    return redirect(url_for('index'))

