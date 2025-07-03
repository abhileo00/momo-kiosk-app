
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import hashlib
import shutil
import os

# Database Configuration
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Hashing function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        customer TEXT,
        items TEXT,
        total REAL,
        payment_mode TEXT,
        status TEXT,
        staff TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        phone TEXT,
        credit_balance REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        item TEXT UNIQUE,
        price REAL,
        cost REAL,
        stock INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        access_pages TEXT
    )""")
    # Add default admin
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, access_pages) VALUES (?, ?, ?, ?)",
                  ("admin", hash_password("admin123"), "Admin", "Orders,Customers,Inventory,Reports,Backup,Accounts"))
    conn.commit()
    return conn

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT password, role, access_pages FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and result[0] == hash_password(password):
        return result[1], result[2].split(",")
    return None, []

# Connect DB
conn = init_db()

# Session State Init
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_pages' not in st.session_state:
    st.session_state.user_pages = []

# Login Page
if not st.session_state.current_user:
    st.title("Food Order Pro - Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            role, pages = authenticate(username, password)
            if role:
                st.session_state.current_user = username
                st.session_state.user_role = role
                st.session_state.user_pages = pages
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# Tabs Implementation (placeholders for simplicity)
def order_tab():
    st.subheader("Order Booking")
    st.info("This is the Order page.")

def customers_tab():
    st.subheader("Customer Management")
    st.info("This is the Customers page.")

def inventory_tab():
    st.subheader("Inventory Control")
    st.info("This is the Inventory page.")

def reports_tab():
    st.subheader("Sales & Credit Reports")
    st.info("This is the Reports page.")

def backup_tab():
    st.subheader("Database Backup")
    st.info("This is the Backup page.")

def accounts_tab():
    st.subheader("User Management")
    df = pd.read_sql("SELECT username, role, access_pages FROM users", conn)
    st.dataframe(df)

# UI Layout
st.title("Food Order Pro")
st.markdown(f"Welcome **{st.session_state.current_user}** ({st.session_state.user_role})")

pages_dict = {
    "Orders": order_tab,
    "Customers": customers_tab,
    "Inventory": inventory_tab,
    "Reports": reports_tab,
    "Backup": backup_tab,
    "Accounts": accounts_tab,
}

tabs = st.tabs(st.session_state.user_pages)
for i, name in enumerate(st.session_state.user_pages):
    with tabs[i]:
        pages_dict[name]()

# Logout
if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.user_pages = []
    st.rerun()
