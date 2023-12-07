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

@bp_option.route('/updateoption', methods=['POST'])
def updateoption():
    optionid = request.form['id']
    namejp = request.form['namejp']
    nameen = request.form['nameen']
    pricejp = request.form['pricejp']
    priceen = request.form['priceen']

    con = get_db()
    con.execute(
            "UPDATE options SET NAMEJP = ?, NAMEEN = ?, PRICEJP = ?, PRICEEN = ? WHERE id =?",
            [namejp, nameen, pricejp, priceen, optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/deleteoption', methods=['POST'])
def deleteoption():
    optionid = request.form['id']

    con = get_db()
    con.execute(
            "DELETE FROM options WHERE id = ?",
            [optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/selectoption', methods=['POST'])
def selectoption():
    data = request.get_json()
    selectoptions = data.get('array', [])
    stmt_formats = ','.join(['?'] * len(selectoptions))
    con = get_db()
    c = con.cursor()
    c.execute(
        "SELECT * FROM options WHERE id IN(%s)" % stmt_formats, tuple(selectoptions)
    )
    selectoptions = c.fetchall()

    return render_template('option.html', selectoptions = selectoptions)