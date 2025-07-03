import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
from datetime import datetime, timedelta
import json
import time
import os
from pathlib import Path

# ======================
# CONFIGURATION
# ======================
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"
SESSION_TIMEOUT = 1800  # 30 minutes
os.makedirs(BACKUP_DIR, exist_ok=True)

# ======================
# DATABASE SETUP
# ======================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tables
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  role TEXT,
                  permissions TEXT)''')  # JSON: {"orders":True, "inventory":False}
    
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
    
    # Indexes for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON orders(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer)")
    
    # Default admin
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        hashed_pw = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ("admin", hashed_pw, "Admin"))
    
    conn.commit()
    return conn

conn = init_db()

# ======================
# AUTHENTICATION
# ======================
def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT password, role, permissions FROM users WHERE username=?", (username,))
    result = c.fetchone()
    
    if result and bcrypt.checkpw(password.encode(), result[0]):
        st.session_state.update({
            "user": username,
            "role": result[1],
            "permissions": json.loads(result[2]) if result[2] else {},
            "last_activity": datetime.now()
        })
        return True
    return False

# ======================
# ADMIN FUNCTIONS
# ======================
def staff_management():
    st.header("👨‍💼 Staff Accounts")
    
    with st.expander("➕ Create New Staff Account"):
        with st.form("staff_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Staff", "Manager"])
            
            st.subheader("Permissions")
            cols = st.columns(3)
            permissions = {
                "orders": cols[0].checkbox("Orders", True),
                "customers": cols[1].checkbox("Customers", True),
                "inventory": cols[2].checkbox("Inventory", role=="Manager"),
                "reports": cols[0].checkbox("Reports", role=="Manager"),
                "backup": cols[1].checkbox("Backup", False)
            }
            
            if st.form_submit_button("Create Account"):
                hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                conn.execute(
                    "INSERT INTO users (username, password, role, permissions) VALUES (?, ?, ?, ?)",
                    (username, hashed_pw, role, json.dumps(permissions))
                )
                conn.commit()
                st.success(f"Account created for {username}")

    st.subheader("Current Staff")
    staff_df = pd.read_sql("SELECT username, role FROM users WHERE role != 'Admin'", conn)
    st.dataframe(staff_df)

# ======================
# REPORTING SYSTEM
# ======================
def generate_reports():
    st.header("📊 Sales Analytics")
    
    # Date selection
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
    end_date = col2.date_input("End Date", datetime.now())
    
    # Fetch data
    query = f"""
        SELECT * FROM orders 
        WHERE date(timestamp) BETWEEN '{start_date}' AND '{end_date}'
    """
    orders = pd.read_sql(query, conn)
    orders['timestamp'] = pd.to_datetime(orders['timestamp'])
    
    # Time-based reports
    report_type = st.radio("Report Type", 
                         ["Daily Summary", "Weekly Trend", "Monthly Overview", "Item Analysis"])
    
    if report_type == "Daily Summary":
        daily = orders.groupby(orders['timestamp'].dt.date).agg({
            'total': 'sum',
            'id': 'count'
        }).rename(columns={'id': 'orders'})
        st.bar_chart(daily['total'])
        st.dataframe(daily)
    
    elif report_type == "Item Analysis":
        # Parse JSON items column
        all_items = []
        for _, row in orders.iterrows():
            items = json.loads(row['items'])
            for item in items:
                all_items.append({
                    'date': row['timestamp'].date(),
                    'item': item['item'],
                    'qty': item['quantity'],
                    'revenue': item['total']
                })
        
        items_df = pd.DataFrame(all_items)
        top_items = items_df.groupby('item').agg({
            'qty': 'sum',
            'revenue': 'sum'
        }).sort_values('revenue', ascending=False)
        
        st.subheader("Top Selling Items")
        st.dataframe(top_items)

# ======================
# MAIN APP
# ======================
def main():
    st.title("🍔 Food Order Pro")
    
    # Session timeout check
    if "last_activity" in st.session_state:
        inactive = (datetime.now() - st.session_state.last_activity).seconds
        if inactive > SESSION_TIMEOUT:
            st.warning("Session expired")
            st.session_state.clear()
            st.rerun()
        st.session_state.last_activity = datetime.now()
    
    # Navigation
    if st.session_state.role == "Admin":
        tabs = ["Orders", "Customers", "Inventory", "Reports", "Staff", "Backup"]
    else:
        tabs = [tab for tab in ["Orders", "Customers", "Inventory"] 
               if st.session_state.permissions.get(tab.lower(), False)]
    
    selected_tab = st.sidebar.radio("Menu", tabs)
    
    # Tab routing
    if selected_tab == "Staff":
        staff_management()
    elif selected_tab == "Reports":
        generate_reports()
    # ... (other tab implementations)

# ======================
# AUTHENTICATION FLOW
# ======================
if "user" not in st.session_state:
    st.title("🔑 Login")
    with st.form("login"):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if authenticate(user, pw):
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()
else:
    main()
