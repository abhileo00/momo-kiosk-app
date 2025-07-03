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
                  role TEXT)''')
    
    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                 ("admin", hash_password("admin123"), "Admin"))
    
    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT password, role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and result[0] == hash_password(password):
        return result[1]  # Return role
    return None

# Initialize app
conn = init_db()
os.makedirs(BACKUP_DIR, exist_ok=True)

# Session state
if 'current_order' not in st.session_state:
    st.session_state.current_order = []
if 'customer_name' not in st.session_state:
    st.session_state.customer_name = ""
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# Login Screen
if not st.session_state.current_user:
    st.title("Food Order Pro - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            role = authenticate(username, password)
            if role:
                st.session_state.current_user = username
                st.session_state.user_role = role
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# ======================
# TAB CONTENT FUNCTIONS
# ======================

def order_tab():
    st.header("New Order")
    
    # Customer Section
    customer_name = st.text_input(
        "Customer Name", 
        value=st.session_state.customer_name,
        placeholder="Enter name for credit or 'Walk-in'"
    )
    st.session_state.customer_name = customer_name
    
    # Menu Selection
    menu_df = pd.read_sql("SELECT * FROM menu WHERE stock > 0", conn)
    categories = menu_df['category'].unique()
    
    category = st.selectbox("Select Category", categories)
    items = menu_df[menu_df['category'] == category]
    
    for _, item in items.iterrows():
        with st.expander(f"{item['item']} - ₹{item['price']} (Stock: {item['stock']})"):
            qty = st.number_input(
                "Quantity", 
                min_value=0, 
                max_value=item['stock'],
                key=f"qty_{item['item']}"
            )
            
            if qty > 0 and st.button(f"Add {item['item']}", key=f"add_{item['item']}"):
                order_item = {
                    "item": item['item'],
                    "price": item['price'],
                    "quantity": qty,
                    "total": item['price'] * qty
                }
                st.session_state.current_order.append(order_item)
                
                # Update stock
                conn.execute("UPDATE menu SET stock = stock - ? WHERE item = ?", 
                           (qty, item['item']))
                conn.commit()
                
                st.success(f"Added {qty} × {item['item']}")
                time.sleep(0.5)
                st.rerun()
    
    # Order Summary
    if st.session_state.current_order:
        st.subheader("Order Summary")
        order_df = pd.DataFrame(st.session_state.current_order)
        st.dataframe(order_df)
        
        total = order_df['total'].sum()
        st.markdown(f"**Total: ₹{total}**")
        
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online"])
        
        if st.button("Submit Order"):
            # Save order
            order_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer": customer_name,
                "items": str(st.session_state.current_order),
                "total": total,
                "payment_mode": payment_mode,
                "status": "Completed",
                "staff": st.session_state.current_user
            }
            
            if payment_mode == "Credit" and customer_name:
                # Update customer credit
                conn.execute("""
                    INSERT OR IGNORE INTO customers (name) VALUES (?)
                """, (customer_name,))
                
                conn.execute("""
                    UPDATE customers 
                    SET credit_balance = credit_balance + ?,
                        total_orders = total_orders + 1,
                        total_spent = total_spent + ?
                    WHERE name = ?
                """, (total, total, customer_name))
            
            # Save order
            order_df = pd.DataFrame([order_data])
            order_df.to_sql('orders', conn, if_exists='append', index=False)
            
            st.success("Order submitted successfully!")
            st.session_state.current_order = []
            time.sleep(1)
            st.rerun()

def customers_tab():
    st.header("Customer Management")
    
    tab1, tab2 = st.tabs(["View Customers", "Add/Edit Customer"])
    
    with tab1:
        customers = pd.read_sql("SELECT * FROM customers", conn)
        if not customers.empty:
            st.dataframe(customers)
        else:
            st.info("No customers found")
    
    with tab2:
        with st.form("customer_form"):
            name = st.text_input("Full Name")
            phone = st.text_input("Phone Number")
            credit = st.number_input("Credit Balance", min_value=0.0, value=0.0)
            
            if st.form_submit_button("Save Customer"):
                conn.execute("""
                    INSERT OR REPLACE INTO customers 
                    (name, phone, credit_balance) 
                    VALUES (?, ?, ?)
                """, (name, phone, credit))
                conn.commit()
                st.success("Customer saved successfully!")
                st.rerun()

def inventory_tab():
    st.header("Inventory Management")
    
    menu_items = pd.read_sql("SELECT * FROM menu", conn)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Current Inventory")
        edited_items = st.data_editor(
            menu_items,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", min_value=0)
            },
            key="inventory_editor"
        )
        
        if st.button("Update Inventory"):
            edited_items.to_sql('menu', conn, if_exists='replace', index=False)
            st.success("Inventory updated!")
            st.rerun()
    
    with col2:
        st.subheader("Add New Item")
        with st.form("new_item_form"):
            category = st.selectbox("Category", ["Momos", "Sandwich", "Maggi"])
            item = st.text_input("Item Name")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Initial Stock", min_value=0)
            
            if st.form_submit_button("Add Item"):
                conn.execute("""
                    INSERT INTO menu 
                    (category, item, price, cost, stock) 
                    VALUES (?, ?, ?, ?, ?)
                """, (category, item, price, cost, stock))
                conn.commit()
                st.success("Item added to menu!")
                st.rerun()

def reports_tab():
    st.header("Sales Reports")
    
    orders = pd.read_sql("SELECT * FROM orders", conn)
    
    if orders.empty:
        st.info("No orders found")
        return
    
    orders['timestamp'] = pd.to_datetime(orders['timestamp'])
    orders['date'] = orders['timestamp'].dt.date
    
    tab1, tab2, tab3 = st.tabs(["Daily Sales", "Customer Analysis", "Menu Performance"])
    
    with tab1:
        st.subheader("Daily Sales")
        daily_sales = orders.groupby('date')['total'].sum().reset_index()
        st.bar_chart(daily_sales, x="date", y="total")
        st.dataframe(daily_sales)
    
    with tab2:
        st.subheader("Customer Analysis")
        customer_stats = orders.groupby('customer').agg({
            'total': 'sum',
            'id': 'count'
        }).rename(columns={'id': 'order_count'})
        st.dataframe(customer_stats)
    
    with tab3:
        st.subheader("Menu Performance")
        # Need to explode items for proper analysis
        st.warning("Menu performance analysis requires data processing")
        # Implementation would parse the items column

def backup_tab():
    st.header("System Backup")
    
    if st.button("Create Backup"):
        backup_file = f"{BACKUP_DIR}backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_FILE, backup_file)
        st.success(f"Backup created: {backup_file}")
        st.rerun()
    
    st.subheader("Available Backups")
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')], reverse=True)
    
    if backups:
        selected = st.selectbox("Select backup", backups)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Restore Backup"):
                shutil.copy2(f"{BACKUP_DIR}{selected}", DB_FILE)
                st.success("Database restored! Please refresh the page.")
        with col2:
            if st.button("Delete Backup"):
                os.remove(f"{BACKUP_DIR}{selected}")
                st.success("Backup deleted!")
                st.rerun()
        
        st.write(f"Selected: {selected}")
    else:
        st.info("No backups available")

# ======================
# MAIN APP LAYOUT
# ======================

st.title("Food Order Pro")
st.markdown(f"Logged in as: **{st.session_state.current_user}** ({st.session_state.user_role})")

# Role-based tabs
if st.session_state.user_role == "Admin":
    tabs = st.tabs(["Orders", "Customers", "Inventory", "Reports", "Backup"])
    with tabs[0]:
        order_tab()
    with tabs[1]:
        customers_tab()
    with tabs[2]:
        inventory_tab()
    with tabs[3]:
        reports_tab()
    with tabs[4]:
        backup_tab()
else:  # Staff
    tabs = st.tabs(["Orders", "Customers"])
    with tabs[0]:
        order_tab()
    with tabs[1]:
        customers_tab()

# Logout button
if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.rerun()
