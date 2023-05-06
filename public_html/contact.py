import sqlite3
from flask import Flask , render_template , request , g , redirect , url_for , session 
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash

bp_contact = Blueprint('contact', __name__)

@bp_contact.route('/contact')