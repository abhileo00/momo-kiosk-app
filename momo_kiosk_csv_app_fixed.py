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
                  phone TEXT,
                  items TEXT,
                  total REAL,
                  payment_mode TEXT,
                  status TEXT,
                  staff TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  phone TEXT UNIQUE,
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
                  can_access_orders BOOLEAN DEFAULT 1,
                  can_access_customers BOOLEAN DEFAULT 1,
                  can_access_inventory BOOLEAN DEFAULT 0,
                  can_access_reports BOOLEAN DEFAULT 0,
                  can_access_backup BOOLEAN DEFAULT 0)''')
    
    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("""INSERT INTO users 
                    (username, password, role, can_access_orders, can_access_customers, 
                     can_access_inventory, can_access_reports, can_access_backup) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                 ("admin", hash_password("admin123"), "Admin", 1, 1, 1, 1, 1))
    
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

def get_user_permissions(username):
    c = conn.cursor()
    c.execute("""SELECT can_access_orders, can_access_customers, can_access_inventory,
                 can_access_reports, can_access_backup FROM users WHERE username = ?""", (username,))
    result = c.fetchone()
    if result:
        return {
            "orders": bool(result[0]),
            "customers": bool(result[1]),
            "inventory": bool(result[2]),
            "reports": bool(result[3]),
            "backup": bool(result[4])
        }
    return None

# Initialize app
conn = init_db()
os.makedirs(BACKUP_DIR, exist_ok=True)

# Session state
if 'current_order' not in st.session_state:
    st.session_state.current_order = []
if 'customer_name' not in st.session_state:
    st.session_state.customer_name = "Guest"
if 'customer_phone' not in st.session_state:
    st.session_state.customer_phone = ""
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_permissions' not in st.session_state:
    st.session_state.user_permissions = None

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
                st.session_state.user_permissions = get_user_permissions(username)
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
    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input(
            "Customer Name", 
            value=st.session_state.customer_name,
            placeholder="Enter name (default: Guest)"
        )
        st.session_state.customer_name = customer_name
    
    with col2:
        customer_phone = st.text_input(
            "Phone Number",
            value=st.session_state.customer_phone,
            placeholder="Enter phone for credit customers"
        )
        st.session_state.customer_phone = customer_phone
    
    # Menu Selection
    menu_df = pd.read_sql("SELECT * FROM menu WHERE stock > 0", conn)
    categories = menu_df['category'].unique()
    
    if categories.size > 0:
        category = st.selectbox("Select Category", categories)
        items = menu_df[menu_df['category'] == category]
    else:
        st.warning("No menu items available")
        items = pd.DataFrame()
    
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
            # Handle credit payment validation
            if payment_mode == "Credit":
                if not customer_phone or len(customer_phone) < 10:
                    st.error("Phone number is required for credit payments (minimum 10 digits)")
                    return
                
                # Register customer if not exists
                conn.execute("""
                    INSERT OR IGNORE INTO customers (name, phone) VALUES (?, ?)
                """, (customer_name, customer_phone))
                
                # Update customer credit
                conn.execute("""
                    UPDATE customers 
                    SET credit_balance = credit_balance + ?,
                        total_orders = total_orders + 1,
                        total_spent = total_spent + ?
                    WHERE phone = ?
                """, (total, total, customer_phone))
                conn.commit()
            
            # Save order
            order_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer": customer_name,
                "phone": customer_phone if payment_mode == "Credit" else "",
                "items": str(st.session_state.current_order),
                "total": total,
                "payment_mode": payment_mode,
                "status": "Completed",
                "staff": st.session_state.current_user
            }
            
            order_df = pd.DataFrame([order_data])
            order_df.to_sql('orders', conn, if_exists='append', index=False)
            
            st.success("Order submitted successfully!")
            
            # Reset order state but keep customer info
            st.session_state.current_order = []
            time.sleep(1)
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
            # Changed from selectbox to text_input for free-form category entry
            category = st.text_input("Category", placeholder="e.g., Momos, Sandwich, Maggi")
            item = st.text_input("Item Name")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Initial Stock", min_value=0)
            
            if st.form_submit_button("Add Item"):
                if not category or not item:
                    st.error("Category and Item Name are required!")
                else:
                    conn.execute("""
                        INSERT INTO menu 
                        (category, item, price, cost, stock) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (category.strip(), item.strip(), price, cost, stock))
                    conn.commit()
                    st.success("Item added to menu!")
                    st.rerun()

# ... [Rest of the code remains the same, including customers_tab, reports_tab, backup_tab, staff_management_tab] ...

# ======================
# MAIN APP LAYOUT
# ======================

st.title("Food Order Pro")
st.markdown(f"Logged in as: **{st.session_state.current_user}** ({st.session_state.user_role})")

# Create tabs based on user permissions
tabs_to_show = []
tab_functions = []

if st.session_state.user_permissions["orders"]:
    tabs_to_show.append("Orders")
    tab_functions.append(order_tab)

if st.session_state.user_permissions["customers"]:
    tabs_to_show.append("Customers")
    tab_functions.append(customers_tab)

if st.session_state.user_permissions["inventory"]:
    tabs_to_show.append("Inventory")
    tab_functions.append(inventory_tab)

if st.session_state.user_permissions["reports"]:
    tabs_to_show.append("Reports")
    tab_functions.append(reports_tab)

if st.session_state.user_permissions["backup"]:
    tabs_to_show.append("Backup")
    tab_functions.append(backup_tab)

# Add Staff Management tab for Admin
if st.session_state.user_role == "Admin":
    tabs_to_show.append("Staff Management")
    tab_functions.append(staff_management_tab)

# Create the tabs
tabs = st.tabs(tabs_to_show)

# Display the appropriate content for each tab
for i, tab in enumerate(tabs):
    with tab:
        tab_functions[i]()

# Logout button
if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.user_permissions = None
    st.rerun()
