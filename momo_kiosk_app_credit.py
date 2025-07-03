1800import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import hashlib
import binascii
from pathlib import Path
import time

# Configuration
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"
SESSION_TIMEOUT = 1800  # 30 minutes
os.makedirs(BACKUP_DIR, exist_ok=True)

# Security Functions
def hash_password(password):
    """Secure password hashing with fallback"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt + key

def verify_password(hashed_pw, input_pw):
    """Verify password with fallback"""
    salt = hashed_pw[:32]
    key = hashed_pw[32:]
    new_key = hashlib.pbkdf2_hmac('sha256', input_pw.encode(), salt, 100000)
    return key == new_key

# Database Setup
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT UNIQUE,
                      password TEXT,
                      role TEXT,
                      permissions TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS orders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT,
                      customer TEXT,
                      items TEXT,
                      total REAL,
                      payment_mode TEXT,
                      status TEXT,
                      staff TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS menu
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      category TEXT,
                      item TEXT UNIQUE,
                      price REAL,
                      cost REAL,
                      stock INTEGER)''')

        # Create default admin if not exists
        c.execute("SELECT 1 FROM users WHERE username='admin'")
        if not c.fetchone():
            hashed_pw = hash_password("admin123")
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      ("admin", hashed_pw, "Admin"))
        
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Database initialization failed: {str(e)}")
        return None

conn = init_db()

# Authentication
def authenticate(username, password):
    try:
        c = conn.cursor()
        c.execute("SELECT password, role, permissions FROM users WHERE username=?", (username,))
        result = c.fetchone()
        
        if result and verify_password(result[0], password):
            st.session_state.update({
                "user": username,
                "role": result[1],
                "permissions": json.loads(result[2]) if result[2] else {},
                "last_activity": datetime.now()
            })
            return True
        return False
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return False

# Admin Functions
def staff_management():
    st.header("Staff Management")
    
    with st.expander("Create New Staff Account"):
        with st.form("staff_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Staff", "Manager"])
            
            st.subheader("Permissions")
