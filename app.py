from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import hashlib

app = Flask(__name__)
socketio = SocketIO(app)
app.secret_key = 'rasel_secret_key_2026'

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT
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
    username = request.form['username']
    password = hash_password(request.form['password'])
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['username'] = username
        return redirect(url_for('dashboard'))
    else:
        return render_template('index.html', error="Invalid username or password!")

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def signup_post():
    username = request.form['username']
    password = hash_password(request.form['password'])
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    except sqlite3.IntegrityError:
        return render_template('signup.html', error="Username already exists!")

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute('SELECT * FROM contacts WHERE owner=?', (session['username'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('dashboard.html',
                           username=session['username'],
                           total_users=total_users,
                           contacts=contacts)

@app.route('/add_contact', methods=['POST'])
def add_contact():
    if 'username' not in session:
        return redirect(url_for('home'))
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO contacts (owner, name, phone, email) VALUES (?, ?, ?, ?)',
              (session['username'], name, phone, email))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/delete_contact/<int:contact_id>')
def delete_contact(contact_id):
    if 'username' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM contacts WHERE id=? AND owner=?', (contact_id, session['username']))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/contacts')
def contacts():
    if 'username' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM contacts WHERE owner=?', (session['username'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('contacts.html',
                           username=session['username'],
                           contacts=contacts)

@app.route('/calllog')
def calllog():
    if 'username' not in session:
        return redirect(url_for('home'))
    return render_template('calllog.html', username=session['username'])

@app.route('/messages')
def messages():
    if 'username' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM contacts WHERE owner=?', (session['username'],))
    contacts = c.fetchall()
    conn.close()
    return render_template('messages.html',
                           username=session['username'],
                           contacts=contacts)

@app.route('/chat/<receiver>')
def chat(receiver):
    if 'username' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM messages
                 WHERE (sender=? AND receiver=?)
                 OR (sender=? AND receiver=?)
                 ORDER BY timestamp ASC''',
              (session['username'], receiver, receiver, session['username']))
    chats = c.fetchall()
    conn.close()
    return render_template('chat.html',
                           username=session['username'],
                           receiver=receiver,
                           chats=chats)

@app.route('/send_message_ajax', methods=['POST'])
def send_message_ajax():
    if 'username' not in session:
        return jsonify({'error': 'not logged in'}), 401
    data = request.get_json()
    receiver = data['receiver']
    message = data['message']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)',
              (session['username'], receiver, message))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('home'))
    return render_template('settings.html', username=session['username'])

@app.route('/sport')
def sport():
    return render_template('sport.html')

@app.route('/call/<receiver>')
def call(receiver):
    if 'username' not in session:
        return redirect(url_for('home'))
    return render_template('call.html',
                           username=session['username'],
                           receiver=receiver)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@socketio.on('join_call')
def on_join_call(data):
    join_room(data['room'])
    if data['caller'] != data['receiver']:
        emit('incoming_call_notify', {
            'caller': data['caller'],
            'receiver': data['receiver']
        }, room=data['receiver'])

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
    