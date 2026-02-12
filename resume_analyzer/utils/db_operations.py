import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    # Create results table with additional columns
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            job_description TEXT,
            resume_file TEXT,
            skills TEXT,
            result TEXT,
            matches REAL,
            date TEXT,
            education_result BOOLEAN,
            education_score REAL,
            experience_result BOOLEAN,
            experience_score REAL,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    if result and result[0] == password:
        return True
    return False

def save_result(username, job_desc, resume_file, skills, result, matches, education_result, education_score, experience_result, experience_score):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO results (username, job_description, resume_file, skills, result, matches, date, education_result, education_score, experience_result, experience_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (username, job_desc, resume_file, skills, result, matches, date, education_result, education_score, experience_result, experience_score))
    conn.commit()
    conn.close()

def get_results(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, job_description, resume_file, skills, result, matches, date, education_result, education_score, experience_result, experience_score
        FROM results WHERE username = ?
        ORDER BY date DESC
    ''', (username,))
    results = c.fetchall()
    conn.close()
    return results