import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session , flash
from datetime import timedelta
from editpage import bp_editpage

app = Flask(__name__)
app.register_blueprint(bp_editpage)
app.secret_key = "aaa"
app.permanent_session_lifetime = timedelta(minutes=30)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('nintahp.db')
    return g.db

@app.route('/')
def index():
    return render_template('home.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/HOME】')

if __name__ == '__main__':
    app.run(debug=True)
