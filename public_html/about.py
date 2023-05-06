import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash

bp_about = Blueprint('about', __name__)

@bp_about.route('/about')