# momo_kiosk_csv_app_fixed.py

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import hashlib
import shutil
import os
from pathlib import Path

# Database Configuration
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

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
                  access_pages TEXT)''')

    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, access_pages) VALUES (?, ?, ?, ?)", 
                 ("admin", hash_password("admin123"), "Admin", "Orders,Customers,Inventory,Reports,Backup,Users"))

    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT password, role, access_pages FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and result[0] == hash_password(password):
        return result[1], result[2].split(',')  # role, page access list
    return None, []

# Initialize app
conn = init_db()
os.makedirs(BACKUP_DIR, exist_ok=True)

# Session state
st.set_page_config(page_title="Food Order Pro", layout="wide")
if 'current_order' not in st.session_state:
    st.session_state.current_order = []
if 'customer_name' not in st.session_state:
    st.session_state.customer_name = ""
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_pages' not in st.session_state:
    st.session_state.user_pages = []

# Login Screen
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

# [Modules like order_tab, customers_tab, inventory_tab, reports_tab, backup_tab go here]
# [User manager tab to be included too]

# Top menu navigation
menu_tabs = {
    "Orders": order_tab,
    "Customers": customers_tab,
    "Inventory": inventory_tab,
    "Reports": reports_tab,
    "Backup": backup_tab,
    "Users": user_management_tab  # To be implemented
}

st.title("Food Order Pro")
st.markdown(f"Logged in as: **{st.session_state.current_user}** ({st.session_state.user_role})")

# Render only allowed tabs
available_tabs = [tab for tab in menu_tabs if tab in st.session_state.user_pages]
tabs = st.tabs(available_tabs)
for tab_name, tab_func in zip(available_tabs, tabs):
    with tab_func:
        menu_tabs[tab_name]()

if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.user_pages = []
    st.rerun()
  
