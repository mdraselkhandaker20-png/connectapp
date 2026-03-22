from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import hashlib
import os
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'rasel_secret_key_2026'
socketio = SocketIO(app, cors_allowed_origins="*")

def get_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    else:
        conn = sqlite3.connect('users.db')
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            owner_email TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_phone TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_phone TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = hash_password(request.form['password'])
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email=%s AND password=%s' if os.environ.get('DATABASE_URL') else 'SELECT * FROM users WHERE email=? AND password=?', (email, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['email'] = user[1]
        session['name'] = user[3]
        return redirect(url_for('dashboard'))
    else:
        return render_template('index.html', error="Invalid email or password!")

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def signup_post():
    email = request.form['email']
    password = hash_password(request.form['password'])
    name = request.form['name']
    phone = request.form.get('phone', '')
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(f'INSERT INTO users (email, password, name, phone) VALUES ({ph}, {ph}, {ph}, {ph})',
                  (email, password, name, phone))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    except Exception:
        return render_template('signup.html', error="Email already exists!")

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute(f'SELECT * FROM contacts WHERE owner_email={ph}', (session['email'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('dashboard.html',
                           username=session['name'],
                           email=session['email'],
                           total_users=total_users,
                           contacts=contacts)

@app.route('/add_contact', methods=['POST'])
def add_contact():
    if 'email' not in session:
        return redirect(url_for('home'))
    contact_email = request.form['contact_email']
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'SELECT name, phone FROM users WHERE email={ph}', (contact_email,))
    user = c.fetchone()
    if not user:
        conn.close()
        return render_template('dashboard.html',
                               username=session['name'],
                               email=session['email'],
                               total_users=0,
                               contacts=[],
                               error="No user found with this email!")
    c.execute(f'SELECT * FROM contacts WHERE owner_email={ph} AND contact_email={ph}',
              (session['email'], contact_email))
    exists = c.fetchone()
    if exists:
        conn.close()
        return redirect(url_for('dashboard'))
    c.execute(f'INSERT INTO contacts (owner_email, contact_email, contact_name, contact_phone) VALUES ({ph}, {ph}, {ph}, {ph})',
              (session['email'], contact_email, user[0], user[1]))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/delete_contact/<int:contact_id>')
def delete_contact(contact_id):
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'DELETE FROM contacts WHERE id={ph} AND owner_email={ph}', (contact_id, session['email']))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/contacts')
def contacts():
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'SELECT * FROM contacts WHERE owner_email={ph}', (session['email'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('contacts.html',
                           username=session['name'],
                           email=session['email'],
                           contacts=contacts)

@app.route('/calllog')
def calllog():
    if 'email' not in session:
        return redirect(url_for('home'))
    return render_template('calllog.html', username=session['name'])

@app.route('/messages')
def messages():
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'SELECT * FROM contacts WHERE owner_email={ph}', (session['email'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('messages.html',
                           username=session['name'],
                           email=session['email'],
                           contacts=contacts)

@app.route('/chat/<receiver_email>')
def chat(receiver_email):
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'''SELECT * FROM messages
                 WHERE (sender={ph} AND receiver={ph})
                 OR (sender={ph} AND receiver={ph})
                 ORDER BY timestamp ASC''',
              (session['email'], receiver_email, receiver_email, session['email']))
    chats = c.fetchall()
    c.execute(f'SELECT name FROM users WHERE email={ph}', (receiver_email,))
    receiver = c.fetchone()
    receiver_name = receiver[0] if receiver else receiver_email
    conn.close()
    return render_template('chat.html',
                           username=session['name'],
                           email=session['email'],
                           receiver=receiver_email,
                           receiver_name=receiver_name,
                           chats=chats)

@app.route('/send_message_ajax', methods=['POST'])
def send_message_ajax():
    if 'email' not in session:
        return jsonify({'error': 'not logged in'}), 401
    data = request.get_json()
    receiver = data['receiver']
    message = data['message']
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'INSERT INTO messages (sender, receiver, message) VALUES ({ph}, {ph}, {ph})',
              (session['email'], receiver, message))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/call/<receiver_email>')
def call(receiver_email):
    if 'email' not in session:
        return redirect(url_for('home'))
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    c = conn.cursor()
    c.execute(f'SELECT name FROM users WHERE email={ph}', (receiver_email,))
    receiver = c.fetchone()
    receiver_name = receiver[0] if receiver else receiver_email
    conn.close()
    return render_template('call.html',
                           username=session['name'],
                           email=session['email'],
                           receiver=receiver_email,
                           receiver_name=receiver_name)

@app.route('/settings')
def settings():
    if 'email' not in session:
        return redirect(url_for('home'))
    return render_template('settings.html',
                           username=session['name'],
                           email=session['email'])

@app.route('/sport')
def sport():
    return render_template('sport.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@socketio.on('join_call')
def on_join_call(data):
    join_room(data['room'])
    if data['caller'] != data['receiver']:
        emit('incoming_call_notify', {
            'caller': data['caller'],
            'receiver': data['receiver']
        }, room=data['receiver'])

@socketio.on('join_personal')
def on_join_personal(data):
    join_room(data['username'])

@socketio.on('call_offer')
def on_call_offer(data):
    emit('call_offer', data, room=data['room'])

@socketio.on('call_answer')
def on_call_answer(data):
    emit('call_answer', data, room=data['room'])

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    emit('ice_candidate', data, room=data['room'])

@socketio.on('call_end')
def on_call_end(data):
    emit('call_end', data, room=data['room'], include_self=False)

@socketio.on('call_declined')
def on_call_declined(data):
    emit('call_declined', data, room=data['caller'])

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
