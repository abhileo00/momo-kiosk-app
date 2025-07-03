import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import hashlib
import shutil
import os
from pathlib import Path
Database Configuration

DB_FILE = "food_orders.db" BACKUP_DIR = "backups/"

Initialize database

def init_db(): conn = sqlite3.connect(DB_FILE) c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS orders
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT,
              customer TEXT,
              items TEXT,
              total REAL,
              payment_mode TEXT,
              status TEXT,
              staff TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS customers
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT UNIQUE,
              phone TEXT,
              credit_balance REAL DEFAULT 0,
              total_orders INTEGER DEFAULT 0,
              total_spent REAL DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS menu
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              category TEXT,
              item TEXT UNIQUE,
              price REAL,
              cost REAL,
              stock INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE,
              password TEXT,
              role TEXT,
              access TEXT)''')

# Insert default admin if not exists
c.execute("SELECT 1 FROM users WHERE username='admin'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role, access) VALUES (?, ?, ?, ?)",
              ("admin", hash_password("admin123"), "Admin", "Orders,Customers,Inventory,Reports,Backup,Users"))

conn.commit()
return conn

def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password): c = conn.cursor() c.execute("SELECT password, role, access FROM users WHERE username = ?", (username,)) result = c.fetchone() if result and result[0] == hash_password(password): return result[1], result[2].split(',') return None, []

Initialize app

conn = init_db() os.makedirs(BACKUP_DIR, exist_ok=True)

Session state

for key, default in { 'current_order': [], 'customer_name': "", 'current_user': None, 'user_role': None, 'page_access': [] }.items(): if key not in st.session_state: st.session_state[key] = default

Login Screen

if not st.session_state.current_user: st.title("Food Order Pro - Login") with st.form("login_form"): username = st.text_input("Username") password = st.text_input("Password", type="password") if st.form_submit_button("Login"): role, access = authenticate(username, password) if role: st.session_state.current_user = username st.session_state.user_role = role st.session_state.page_access = access st.rerun() else: st.error("Invalid credentials") st.stop()

Page functions (unchanged: order_tab, customers_tab, inventory_tab, reports_tab, backup_tab)

Add User Management Page

def users_tab(): st.header("User Management") df = pd.read_sql("SELECT username, role, access FROM users", conn) st.dataframe(df)

with st.form("add_user_form"):
    username = st.text_input("New Username")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["Admin", "Staff"])
    access = st.multiselect("Page Access", ["Orders", "Customers", "Inventory", "Reports", "Backup"])
    if st.form_submit_button("Add User"):
        try:
            conn.execute("INSERT INTO users (username, password, role, access) VALUES (?, ?, ?, ?)",
                         (username, hash_password(password), role, ','.join(access)))
            conn.commit()
            st.success("User added successfully")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Username already exists")

Page Navigation

pages = { "Orders": order_tab, "Customers": customers_tab, "Inventory": inventory_tab, "Reports": reports_tab, "Backup": backup_tab, "Users": users_tab }

Display app

st.title("Food Order Pro") st.markdown(f"Logged in as: {st.session_state.current_user} ({st.session_state.user_role})")

visible_pages = st.session_state.page_access if st.session_state.user_role != "Admin" else list(pages.keys()) selected = st.selectbox("Select Page", visible_pages) pagesselected

if st.sidebar.button("Logout"): st.session_state.current_user = None st.session_state.user_role = None st.session_state.page_access = [] st.rerun()

