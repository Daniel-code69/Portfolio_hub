import os
import sqlite3
import functools
import shutil
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, g, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras

# --- APP INITIALIZATION & CONFIGURATION ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'zip', 'html', 'css', 'js', 'py'}

# --- THIS IS YOUR PERSONAL DATABASE URL ---
DATABASE_URL = "postgresql://neondb_owner:npg_OWnbBc4uad9X@ep-bold-cloud-a17yeyx7-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

app.config['SECRET_KEY'] = 'dev-secret-key-change-this-later'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE MANAGEMENT (FOR POSTGRESQL) ---
def get_db_connection():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db

@app.teardown_appcontext
def close_db_connection(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS portfolios (
            id SERIAL PRIMARY KEY,
            student_name TEXT NOT NULL,
            student_id TEXT NOT NULL,
            email TEXT NOT NULL,
            portfolio_title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            project_url TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')
    conn.commit()
    cur.close()

# --- HELPER FUNCTIONS & DECORATORS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    if user_id is not None:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        g.user = cur.fetchone()
        cur.close()

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest': abort(401)
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# --- ROUTE DEFINITIONS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        error = None
        if not username: error = 'Username is required.'
        elif not password: error = 'Password is required.'
        if error is None:
            try:
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)",(username, generate_password_hash(password)))
                conn.commit()
            except psycopg2.IntegrityError:
                error = f"User '{username}' is already registered."
                conn.rollback()
            else:
                flash('Registration successful! Please log in.', 'success')
                cur.close()
                return redirect(url_for("login"))
        flash(error, 'error')
        cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        error = None
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        if user is None or not check_password_hash(user['password'], password):
            error = 'Incorrect username or password.'
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash(error, 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_portfolio():
    data = {k: request.form[k] for k in ['student_name', 'student_id', 'email', 'portfolio_title', 'description', 'category', 'project_url']}
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO portfolios (user_id, student_name, student_id, email, portfolio_title, description, category, project_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
        (g.user['id'], *data.values())
    )
    portfolio_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    files = request.files.getlist('files')
    if files:
        portfolio_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(portfolio_id))
        os.makedirs(portfolio_upload_path, exist_ok=True)
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(portfolio_upload_path, filename))
    return jsonify({'message': 'Portfolio uploaded successfully!', 'status': 'success'}), 201

@app.route('/portfolios')
def get_portfolios():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT p.*, u.username as owner_username FROM portfolios p JOIN users u ON p.user_id = u.id ORDER BY p.upload_date DESC')
    portfolios_data = cur.fetchall()
    cur.close()
    portfolios_list = [dict(p) for p in portfolios_data]
    for portfolio in portfolios_list:
        try:
            portfolio_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(portfolio['id']))
            portfolio['files'] = os.listdir(portfolio_upload_path) if os.path.exists(portfolio_upload_path) else []
        except OSError: portfolio['files'] = []
    return jsonify(portfolios_list)

@app.route('/download/<int:portfolio_id>/<filename>')
def download_file(portfolio_id, filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], str(portfolio_id))
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/portfolio/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_portfolio(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM portfolios WHERE id = %s', (id,))
    portfolio = cur.fetchone()
    if portfolio is None: abort(404)
    if portfolio['user_id'] != g.user['id']: abort(403)
    if request.method == 'POST':
        data = {k: request.form[k] for k in ['student_name', 'student_id', 'email', 'portfolio_title', 'description', 'category', 'project_url']}
        cur.execute(
            'UPDATE portfolios SET student_name=%s, student_id=%s, email=%s, portfolio_title=%s, description=%s, category=%s, project_url=%s WHERE id=%s',
            (*data.values(), id)
        )
        conn.commit()
        cur.close()
        flash('Portfolio updated successfully!', 'success')
        return redirect(url_for('index'))
    cur.close()
    return render_template('edit_portfolio.html', portfolio=portfolio)

@app.route('/portfolio/<int:id>/delete', methods=['POST'])
@login_required
def delete_portfolio(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM portfolios WHERE id = %s AND user_id = %s', (id, g.user['id']))
    portfolio = cur.fetchone()
    if portfolio:
        cur.execute('DELETE FROM portfolios WHERE id = %s', (id,))
        conn.commit()
        portfolio_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
        if os.path.exists(portfolio_upload_path):
            shutil.rmtree(portfolio_upload_path)
        cur.close()
        return jsonify({'status': 'success', 'message': 'Portfolio deleted.'}), 200
    cur.close()
    return jsonify({'status': 'error', 'message': 'Portfolio not found or you do not have permission.'}), 403

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)