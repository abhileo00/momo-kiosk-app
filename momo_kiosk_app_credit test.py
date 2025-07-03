import streamlit as st import pandas as pd import sqlite3 from datetime import datetime, timedelta import time import hashlib import shutil import os from pathlib import Path import ast

DB_FILE = "food_orders.db" BACKUP_DIR = "backups/"

def init_db(): conn = sqlite3.connect(DB_FILE) c = conn.cursor()

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
              role TEXT)''')

c.execute("SELECT 1 FROM users WHERE username='admin'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
             ("admin", hash_password("admin123"), "Admin"))

conn.commit()
return conn

def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password): c = conn.cursor() c.execute("SELECT password, role FROM users WHERE username = ?", (username,)) result = c.fetchone() if result and result[0] == hash_password(password): return result[1] return None

conn = init_db() os.makedirs(BACKUP_DIR, exist_ok=True)

if 'current_order' not in st.session_state: st.session_state.current_order = [] if 'customer_name' not in st.session_state: st.session_state.customer_name = "" if 'current_user' not in st.session_state: st.session_state.current_user = None if 'user_role' not in st.session_state: st.session_state.user_role = None

if not st.session_state.current_user: st.title("Food Order Pro - Login") with st.form("login_form"): username = st.text_input("Username") password = st.text_input("Password", type="password") if st.form_submit_button("Login"): role = authenticate(username, password) if role: st.session_state.current_user = username st.session_state.user_role = role st.rerun() else: st.error("Invalid credentials") st.stop()

TAB CONTENT FUNCTIONS REMAIN UNCHANGED ...

Only fix made to the manage_tab section below

def manage_tab(): st.header("Staff Account Management") if st.session_state.user_role != "Admin": st.warning("Only administrators can access this page") return

tab1, tab2 = st.tabs(["View Staff", "Add Staff"])
with tab1:
    staff_df = pd.read_sql("SELECT id, username, role FROM users", conn)
    if not staff_df.empty:
        st.dataframe(staff_df)
        staff_to_delete = st.selectbox(
            "Select staff to remove",
            staff_df[staff_df['username'] != 'admin']['username'].tolist() + [None],
            index=0
        )
        if st.button("Remove Staff") and staff_to_delete:
            conn.execute("DELETE FROM users WHERE username = ?", (staff_to_delete,))
            conn.commit()
            st.success(f"Staff {staff_to_delete} removed successfully!")
            st.rerun()
    else:
        st.info("No staff accounts found")

with tab2:
    with st.form("staff_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Staff", "Admin"])
        if st.form_submit_button("Create Staff Account"):
            try:
                conn.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, hash_password(password), role)
                )
                conn.commit()
                st.success("Staff account created successfully!")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username already exists")

REMAINING TABS (order_tab, customers_tab, inventory_tab, reports_tab, backup_tab) REMAIN SAME.

MAIN APP UI REMAINS SAME.

if st.session_state.user_role == "Admin": tabs = st.tabs(["Orders", "Customers", "Inventory", "Reports", "Manage", "Backup"]) with tabs[0]: order_tab() with tabs[1]: customers_tab() with tabs[2]: inventory_tab() with tabs[3]: reports_tab() with tabs[4]: manage_tab() with tabs[5]: backup_tab() else: tabs = st.tabs(["Orders", "Customers"]) with tabs[0]: order_tab() with tabs[1]: customers_tab()

if st.sidebar.button("Logout"): st.session_state.current_user = None st.session_state.user_role = None st.rerun()

