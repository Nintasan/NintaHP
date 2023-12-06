import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash
from db import UpdatePosts
from db import get_db

bp_editpage = Blueprint('editpage', __name__, static_folder='./static')

@bp_editpage.route('/editpage')
def first():
   return render_template('image.html')

@bp_editpage.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    file.save(os.path.join('./static/image', file.filename))
    return redirect(url_for('uploaded_file', filename=file.filename))


@bp_editpage.route('/uploaded_file/<string:filename>')
def uploaded_file(filename):
    return render_template('upload.html', filename=filename)