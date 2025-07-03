import streamlit as st
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
            cols = st.columns(3)
            permissions = {
                "orders": cols[0].checkbox("Orders", True),
                "customers": cols[1].checkbox("Customers", True),
                "inventory": cols[2].checkbox("Inventory", role=="Manager"),
                "reports": cols[0].checkbox("Reports", role=="Manager"),
                "backup": cols[1].checkbox("Backup", False)
            }
            
            if st.form_submit_button("Create Account"):
                try:
                    hashed_pw = hash_password(password)
                    conn.execute(
                        "INSERT INTO users (username, password, role, permissions) VALUES (?, ?, ?, ?)",
                        (username, hashed_pw, role, json.dumps(permissions))
                    conn.commit()
                    st.success(f"Account created for {username}")
                except Exception as e:
                    st.error(f"Error creating account: {str(e)}")

    st.subheader("Current Staff")
    try:
        staff_df = pd.read_sql("SELECT username, role FROM users WHERE role != 'Admin'", conn)
        st.dataframe(staff_df)
    except Exception as e:
        st.error(f"Error loading staff data: {str(e)}")

# Reporting System
def generate_reports():
    st.header("Sales Analytics")
    
    try:
        # Date selection
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
        end_date = col2.date_input("End Date", datetime.now())
        
        # Time period selection
        period = st.selectbox("Report Period", ["Daily", "Weekly", "Monthly"])
        
        # Payment type selection
        payment_type = st.selectbox("Payment Type", ["All", "Cash", "Credit", "Online"])
        
        # Fetch data
        query = f"""
            SELECT * FROM orders 
            WHERE date(timestamp) BETWEEN '{start_date}' AND '{end_date}'
        """
        if payment_type != "All":
            query += f" AND payment_mode = '{payment_type}'"
            
        orders = pd.read_sql(query, conn)
        orders['timestamp'] = pd.to_datetime(orders['timestamp'])
        
        # Generate reports based on period
        if period == "Daily":
            report = orders.groupby(orders['timestamp'].dt.date).agg({
                'total': 'sum',
                'id': 'count'
            }).rename(columns={'id': 'orders'})
        elif period == "Weekly":
            orders['week'] = orders['timestamp'].dt.strftime('%Y-%U')
            report = orders.groupby('week').agg({
                'total': 'sum',
                'id': 'count'
            }).rename(columns={'id': 'orders'})
        else:  # Monthly
            orders['month'] = orders['timestamp'].dt.strftime('%Y-%m')
            report = orders.groupby('month').agg({
                'total': 'sum',
                'id': 'count'
            }).rename(columns={'id': 'orders'})
        
        st.subheader(f"{period} Sales Summary ({payment_type})")
        col1, col2 = st.columns(2)
        col1.bar_chart(report['total'])
        col2.dataframe(report)
        
        # Item-wise sales
        st.subheader("Item-wise Sales")
        try:
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
            
            st.dataframe(top_items)
        except Exception as e:
            st.error(f"Error processing item data: {str(e)}")
            
    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")

# Main App
def main():
    st.title("Food Order Pro")
    
    # Session timeout check
    if "last_activity" in st.session_state:
        inactive = (datetime.now() - st.session_state.last_activity).seconds
        if inactive > SESSION_TIMEOUT:
            st.warning("Session expired - please login again")
            st.session_state.clear()
            time.sleep(2)
            st.rerun()
        st.session_state.last_activity = datetime.now()
    
    # Navigation
    if st.session_state.role == "Admin":
        tabs = ["Orders", "Customers", "Inventory", "Reports", "Staff", "Backup"]
    else:
        tabs = [tab for tab in ["Orders", "Customers", "Inventory", "Reports"] 
               if st.session_state.permissions.get(tab.lower(), False)]
    
    selected_tab = st.sidebar.radio("Menu", tabs)
    
    # Tab routing
    if selected_tab == "Staff":
        staff_management()
    elif selected_tab == "Reports":
        generate_reports()
    elif selected_tab == "Orders":
        st.header("Order Management")
        # Order management implementation would go here
    elif selected_tab == "Customers":
        st.header("Customer Management")
        # Customer management implementation would go here
    elif selected_tab == "Inventory":
        st.header("Inventory Management")
        # Inventory management implementation would go here
    elif selected_tab == "Backup":
        st.header("System Backup")
        # Backup implementation would go here

# Authentication Flow
if "user" not in st.session_state:
    st.title("Login")
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
