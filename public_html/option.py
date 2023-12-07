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
    orders = request.form['orders']
    categories = request.form['categories']

    con = get_db()
    con.execute(
            "INSERT INTO options (NAMEJP, NAMEEN, PRICEJP, PRICEEN, ORDERS, CATEGORIES) VALUES (?, ?, ?, ?, ?, ?)",
            [namejp, nameen, pricejp, priceen, orders, categories]
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
    orders = request.form['orders']
    categories = request.form['categories']

    con = get_db()
    con.execute(
            "UPDATE options SET namejp = ?, nameen = ?, pricejp = ?, priceen = ?, orders = ?, categories = ? WHERE id =?",
            [namejp, nameen, pricejp, priceen, orders, categories, optionid]
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

@bp_option.route('/updateorder', methods=['POST'])
def updateorder():
    optionid = request.form['id']
    neworder = request.form['order']

    con = get_db()
    con.execute(
            "UPDATE options SET orders = ? WHERE id =?",
            [neworder, optionid]
        )
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/addcolumnoption', methods=['POST'])
def addcolumnoption():
    tablename = request.form['tablename']
    columnname = request.form['columnname']
    types = request.form['type']
    defaults = request.form['default']


    con = get_db()
    query = f"ALTER TABLE {tablename} ADD COLUMN {columnname} {types} DEFAULT {defaults}"
    con.execute(query)
    con.commit()
    con.close()

    return redirect(url_for('index'))

@bp_option.route('/plancontent', methods=['POST'])
def plancontent():
    planID = request.form['planID']
    plan1 = request.form['plan1']
    plan2 = request.form['plan2']
    plan3 = request.form['plan3']

    con = get_db()
    con.execute(
            "UPDATE options SET plan1 = ?, plan2 = ?, plan3 = ? WHERE id =?",
            [plan1, plan2, plan3, planID]
        )
    con.commit()
    con.close()

    return redirect(url_for('contact'))

@bp_option.route('/selectoption', methods=['POST'])
def selectoption():
    data = request.get_json()
    selectoptions0 = data.get('array', [])
    stmt_formats = ','.join(['?'] * len(selectoptions0))
    con = get_db()
    c = con.cursor()
    c.execute(
        "SELECT * FROM options WHERE id IN(%s)" % stmt_formats, tuple(selectoptions0)
    )
    selectoptions = c.fetchall()

    c = con.cursor()
    c.execute(
        "SELECT SUM(pricejp), SUM(priceen) FROM options WHERE id IN(%s) ORDER BY orders" % stmt_formats, tuple(selectoptions0)
    )
    sumall = c.fetchone()
    con.close()


    return render_template('option.html', selectoptions = selectoptions, sumall = sumall)