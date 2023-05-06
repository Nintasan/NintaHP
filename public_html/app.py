import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session , flash
from datetime import timedelta
from editpage import bp_editpage
from flask_mail import Mail, Message

app = Flask(__name__, template_folder="templates")

mail =Mail(app)
app.register_blueprint(bp_editpage)
app.secret_key = "aaa"
app.permanent_session_lifetime = timedelta(minutes=30)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('nintahp.db')
    return g.db

@app.route('/')
def home():
    return render_template('home.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/HOME】')

@app.route('/about')
def about():
    return render_template('about.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/About】')

@app.route('/contact')
def contact():
    return render_template('contact.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Contact】')

@app.route('/reply', methods=['POST'])
def reply():
    name = request.form['name']
    email = request.form['email']
    content = request.form['content']

    msg = Message(content,
                  sender=(name, email),
                  recipients=["ninta.illustration@gmail.com"])
    mail.send(msg)


    return render_template('reply.html', title = 'Vtuber art & rig comm【イラストレーター：ニンタ/Reply】')


if __name__ == '__main__':
    app.run(debug=True)
