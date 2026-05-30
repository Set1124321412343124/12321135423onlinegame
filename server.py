import sqlite3
import hashlib
import os
from flask import Flask, request, jsonify, session, render_template

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

DB_PATH = os.path.join(os.path.dirname(__file__), 'game.db')
PORT = int(os.environ.get('PORT', 5000))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


@app.route('/')
def index():
    return render_template('game.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if len(username) < 2:
        return jsonify({'error': 'Минимум 2 символа'}), 400
    if len(password) < 3:
        return jsonify({'error': 'Минимум 3 символа'}), 400

    conn = get_db()
    existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': 'Ник уже занят'}), 400

    conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                 (username, hash_password(password)))
    conn.execute('INSERT INTO scores (username, score) VALUES (?, 0)', (username,))
    conn.commit()
    conn.close()

    session['username'] = username
    return jsonify({'username': username})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    conn = get_db()
    user = conn.execute('SELECT password FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if not user or user['password'] != hash_password(password):
        return jsonify({'error': 'Неверный ник или пароль'}), 400

    session['username'] = username
    return jsonify({'username': username})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'ok': True})


@app.route('/api/me')
def me():
    username = session.get('username')
    if not username:
        return jsonify({'user': None})
    conn = get_db()
    row = conn.execute('SELECT score FROM scores WHERE username = ?', (username,)).fetchone()
    conn.close()
    return jsonify({'user': username, 'score': row['score'] if row else 0})


@app.route('/api/score', methods=['POST'])
def save_score():
    username = session.get('username')
    if not username:
        return jsonify({'error': 'Не авторизован'}), 401

    data = request.get_json()
    new_score = int(data.get('score', 0))

    conn = get_db()
    current = conn.execute('SELECT score FROM scores WHERE username = ?', (username,)).fetchone()
    if current and new_score > current['score']:
        conn.execute('UPDATE scores SET score = ? WHERE username = ?', (new_score, username))
        conn.commit()
    elif current is None:
        conn.execute('INSERT INTO scores (username, score) VALUES (?, ?)', (username, new_score))
        conn.commit()
    conn.close()

    return jsonify({'ok': True, 'score': new_score})


@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    rows = conn.execute(
        'SELECT username, score FROM scores WHERE score > 0 ORDER BY score DESC LIMIT 50'
    ).fetchall()
    conn.close()
    return jsonify([{'name': r['username'], 'score': r['score']} for r in rows])


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
