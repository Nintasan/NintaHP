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
