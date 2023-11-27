import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash

bp_signup = Blueprint('user', __name__)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('vtubedockdata.db')
    return g.db

@bp.route('/signup')
def signup():
    return render_template('signup.html', title = 'Live2DTree signup')

@bp.route('/register', methods=['POST'])
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