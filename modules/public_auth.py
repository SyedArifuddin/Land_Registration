from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import mysql.connector
from auth import db_config
from blockchain_config import land_chain

citizen_bp = Blueprint('citizen', __name__)

@citizen_bp.route('/citizen/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            # SAVES TO DB: Creates a new public user
            cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', (user, pw, 'citizen'))
            conn.commit()
            conn.close()
            flash("Account created! Please Sign In.")
            return redirect(url_for('citizen.login'))
        except mysql.connector.Error:
            flash("Username already exists.")
    return render_template('public_auth.html', mode='signup')

@citizen_bp.route('/citizen/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        # Verify credentials for public users only
        cursor.execute('SELECT * FROM users WHERE username=%s AND password=%s AND role=%s', (user, pw, 'citizen'))
        account = cursor.fetchone()
        conn.close()

        if account:
            session['user'] = account['username']
            session['role'] = 'citizen'
            return redirect(url_for('citizen.dashboard'))
        else:
            flash("Invalid Public User credentials.")
    return render_template('public_auth.html', mode='login')

@citizen_bp.route('/citizen/dashboard')
def dashboard():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    return render_template('public_dashboard.html', user=session['user'], chain=land_chain.chain)