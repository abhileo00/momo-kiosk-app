import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import hashlib
import binascii
import time
import shutil

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
        
        c.execute('''CREATE TABLE IF NOT EXISTS customers
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT UNIQUE,
                      phone TEXT,
                      credit_balance REAL DEFAULT 0)''')

        # Create default admin if not exists
        c.execute("SELECT 1 FROM users WHERE username='admin'")
        if not c.fetchone():
            hashed_pw = hash_password("admin123")
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      ("admin", hashed_pw, "Admin"))
        
        # Create sample menu items if empty
        c.execute("SELECT 1 FROM menu LIMIT 1")
        if not c.fetchone():
            sample_items = [
                ("Appetizer", "Spring Rolls", 4.99, 1.50, 100),
                ("Main", "Chicken Curry", 12.99, 4.00, 50),
                ("Dessert", "Ice Cream", 3.99, 1.00, 30)
            ]
            c.executemany("INSERT INTO menu (category, item, price, cost, stock) VALUES (?, ?, ?, ?, ?)", sample_items)
        
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
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating account: {str(e)}")

    st.subheader("Current Staff")
    try:
        staff_df = pd.read_sql("SELECT username, role FROM users WHERE role != 'Admin'", conn)
        if not staff_df.empty:
            st.dataframe(staff_df)
        else:
            st.info("No staff accounts found")
    except Exception as e:
        st.error(f"Error loading staff data: {str(e)}")

# Order Management
def order_management():
    st.header("Order Management")
    
    # Customer selection
    customers = pd.read_sql("SELECT name, phone FROM customers", conn)
    customer_name = st.selectbox("Customer", ["Walk-in"] + customers['name'].tolist())
    
    # Menu display
    menu = pd.read_sql("SELECT * FROM menu WHERE stock > 0", conn)
    categories = menu['category'].unique()
    
    if 'current_order' not in st.session_state:
        st.session_state.current_order = []
    
    # Category tabs
    tabs = st.tabs([f"📋 {cat}" for cat in categories])
    
    for i, category in enumerate(categories):
        with tabs[i]:
            items = menu[menu['category'] == category]
            for _, item in items.iterrows():
                col1, col2 = st.columns([3,1])
                col1.write(f"**{item['item']}** - ${item['price']:.2f} (Stock: {item['stock']})")
                qty = col2.number_input("Qty", 0, item['stock'], 0, key=f"qty_{item['id']}")
                
                if qty > 0 and col2.button("Add", key=f"add_{item['id']}"):
                    order_item = {
                        "id": item['id'],
                        "item": item['item'],
                        "price": item['price'],
                        "quantity": qty,
                        "total": item['price'] * qty
                    }
                    st.session_state.current_order.append(order_item)
                    st.success(f"Added {qty}x {item['item']}")
                    time.sleep(0.5)
                    st.rerun()
    
    # Order summary
    if st.session_state.current_order:
        st.subheader("Order Summary")
        order_df = pd.DataFrame(st.session_state.current_order)
        st.dataframe(order_df[['item', 'quantity', 'price', 'total']])
        
        total = order_df['total'].sum()
        st.write(f"**Total: ${total:.2f}**")
        
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online"])
        
        if st.button("Submit Order"):
            try:
                # Process order
                order_data = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "customer": customer_name,
                    "items": json.dumps(st.session_state.current_order),
                    "total": total,
                    "payment_mode": payment_mode,
                    "status": "Completed",
                    "staff": st.session_state.user
                }
                
                # Update inventory
                for item in st.session_state.current_order:
                    conn.execute("UPDATE menu SET stock = stock - ? WHERE id = ?", 
                               (item['quantity'], item['id']))
                
                # Update customer credit if applicable
                if payment_mode == "Credit" and customer_name != "Walk-in":
                    conn.execute("UPDATE customers SET credit_balance = credit_balance + ? WHERE name = ?",
                                (total, customer_name))
                
                # Save order
                conn.execute("""
                    INSERT INTO orders (timestamp, customer, items, total, payment_mode, status, staff)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, tuple(order_data.values()))
                
                conn.commit()
                st.success("Order submitted successfully!")
                st.session_state.current_order = []
                time.sleep(1)
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Error processing order: {str(e)}")

# Reporting System
def generate_reports():
    st.header("Sales Analytics")
    
    try:
        # Date selection
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
        end_date = col2.date_input("End Date", datetime.now())
        
        # Report type selection
        report_type = st.selectbox("Report Type", 
                                 ["Sales Summary", "Payment Analysis", "Item Performance"])
        
        # Base query
        query = f"""
            SELECT * FROM orders 
            WHERE date(timestamp) BETWEEN '{start_date}' AND '{end_date}'
        """
        orders = pd.read_sql(query, conn)
        orders['timestamp'] = pd.to_datetime(orders['timestamp'])
        
        if report_type == "Sales Summary":
            st.subheader("Sales Over Time")
            freq = st.radio("Frequency", ["Daily", "Weekly", "Monthly"])
            
            if freq == "Daily":
                sales = orders.groupby(orders['timestamp'].dt.date)['total'].sum()
            elif freq == "Weekly":
                sales = orders.groupby(orders['timestamp'].dt.strftime('%Y-%W'))['total'].sum()
            else:  # Monthly
                sales = orders.groupby(orders['timestamp'].dt.strftime('%Y-%m'))['total'].sum()
            
            st.bar_chart(sales)
            st.dataframe(sales.reset_index().rename(columns={'total':'Amount', 'timestamp':'Period'}))
        
        elif report_type == "Payment Analysis":
            st.subheader("Payment Method Breakdown")
            payments = orders.groupby('payment_mode').agg({
                'total': ['sum', 'count']
            }).rename(columns={'sum':'Total Revenue', 'count':'Transaction Count'})
            
            st.bar_chart(payments['total']['sum'])
            st.dataframe(payments)
        
        elif report_type == "Item Performance":
            st.subheader("Top Selling Items")
            
            # Parse order items
            all_items = []
            for _, row in orders.iterrows():
                items = json.loads(row['items'])
                for item in items:
                    all_items.append({
                        'item': item['item'],
                        'quantity': item['quantity'],
                        'revenue': item['total']
                    })
            
            items_df = pd.DataFrame(all_items)
            top_items = items_df.groupby('item').agg({
                'quantity': 'sum',
                'revenue': 'sum'
            }).sort_values('revenue', ascending=False)
            
            st.dataframe(top_items)
    
    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")

# Backup System
def backup_system():
    st.header("System Backup")
    
    # Create backup
    if st.button("Create Backup Now"):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_FILE, backup_file)
            st.success(f"Backup created: {backup_file}")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Backup failed: {str(e)}")
    
    # Restore backup
    st.subheader("Restore Backup")
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')], reverse=True)
    
    if backups:
        selected = st.selectbox("Select backup to restore", backups)
        
        if st.button(f"Restore {selected}"):
            try:
                shutil.copy2(os.path.join(BACKUP_DIR, selected), DB_FILE)
                st.success("Database restored! Please refresh the page.")
            except Exception as e:
                st.error(f"Restore failed: {str(e)}")
    else:
        st.info("No backups available")

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
        order_management()
    elif selected_tab == "Customers":
        st.header("Customer Management")
        # Implement customer management here
    elif selected_tab == "Inventory":
        st.header("Inventory Management")
        # Implement inventory management here
    elif selected_tab == "Backup":
        backup_system()

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

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
