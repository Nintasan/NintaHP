import sqlite3
import json
from flask import Flask , render_template , request , g , redirect , url_for , session, jsonify
from flask import Blueprint
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

bp_option = Blueprint('option', __name__)

@bp_option.route('/option', methods=['POST'])
def option():
    namejp = request.form['namejp']
    nameen = request.form['nameen']
    pricejp = request.form['pricejp']
    priceen = request.form['priceen']

    con = get_db()
    con.execute(
            "INSERT INTO options (NAMEJP, NAMEEN, PRICEJP, PRICEEN) VALUES (?, ?, ?, ?)",
            [namejp, nameen, pricejp, priceen]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))
@bp_option.route('/selectoption', methods=['POST'])
def selectoption():
    data = request.get_json()
    checkLen1 = data.get('array', [])
    checkLen = len(checkLen1)

    return render_template('option.html', checkLen = checkLen)