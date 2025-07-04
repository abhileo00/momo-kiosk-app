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
                  name TEXT,
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
    
    # Insert some sample menu items if none exist
    c.execute("SELECT 1 FROM menu LIMIT 1")
    if not c.fetchone():
        sample_items = [
            ("Momos", "Veg Momos", 60.0, 30.0, 100),
            ("Momos", "Chicken Momos", 80.0, 40.0, 100),
            ("Sandwich", "Veg Sandwich", 50.0, 25.0, 50),
            ("Sandwich", "Cheese Sandwich", 70.0, 35.0, 50),
            ("Maggi", "Plain Maggi", 40.0, 15.0, 80),
            ("Maggi", "Cheese Maggi", 60.0, 25.0, 80)
        ]
        c.executemany("INSERT INTO menu (category, item, price, cost, stock) VALUES (?, ?, ?, ?, ?)", sample_items)
    
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
    
    if not menu_df.empty:
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
    else:
        st.warning("No menu items available or all items are out of stock")
    
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
            phone = st.text_input("Phone Number (Required)", placeholder="10 digit phone number")
            credit = st.number_input("Credit Balance", min_value=0.0, value=0.0)
            
            if st.form_submit_button("Save Customer"):
                if not phone or len(phone) < 10:
                    st.error("Valid phone number is required (minimum 10 digits)")
                else:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO customers 
                            (name, phone, credit_balance) 
                            VALUES (?, ?, ?)
                        """, (name, phone, credit))
                        conn.commit()
                        st.success("Customer saved successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Phone number already exists for another customer")

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
            category = st.text_input("Category", placeholder="e.g., Momos, Sandwich, Maggi")
            item = st.text_input("Item Name")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Initial Stock", min_value=0)
            
            if st.form_submit_button("Add Item"):
                if not category or not item:
                    st.error("Category and Item Name are required!")
                else:
                    try:
                        conn.execute("""
                            INSERT INTO menu 
                            (category, item, price, cost, stock) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (category.strip(), item.strip(), price, cost, stock))
                        conn.commit()
                        st.success("Item added to menu!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Item name already exists in the menu")

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
        try:
            # Parse the items string to analyze menu performance
            all_items = []
            for _, row in orders.iterrows():
                items = eval(row['items'])  # Note: Using eval is not generally safe, but works for this demo
                for item in items:
                    item['date'] = row['date']
                    all_items.append(item)
            
            if all_items:
                items_df = pd.DataFrame(all_items)
                items_df['date'] = pd.to_datetime(items_df['date'])
                
                # Weekly sales by item
                items_df['week'] = items_df['date'].dt.strftime('%Y-%U')
                weekly_sales = items_df.groupby(['item', 'week'])['quantity'].sum().unstack().fillna(0)
                
                st.write("Weekly Sales by Item")
                st.dataframe(weekly_sales)
                
                # Top selling items
                top_items = items_df.groupby('item')['quantity'].sum().sort_values(ascending=False)
                st.write("Top Selling Items")
                st.dataframe(top_items)
            else:
                st.warning("Could not parse order items for analysis")
        except:
            st.warning("Error analyzing menu performance data")

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

def staff_management_tab():
    st.header("Staff Account Management")
    
    tab1, tab2 = st.tabs(["View Staff", "Add/Edit Staff"])
    
    with tab1:
        staff_df = pd.read_sql("SELECT id, username, role FROM users", conn)
        if not staff_df.empty:
            st.dataframe(staff_df)
            
            # Delete staff option
            staff_to_delete = st.selectbox("Select staff to delete", 
                                        staff_df['username'].tolist(),
                                        key="delete_staff_select")
            
            if st.button("Delete Staff Account", key="delete_staff_btn"):
                if staff_to_delete == "admin":
                    st.error("Cannot delete admin account!")
                else:
                    conn.execute("DELETE FROM users WHERE username = ?", (staff_to_delete,))
                    conn.commit()
                    st.success(f"Deleted staff account: {staff_to_delete}")
                    st.rerun()
        else:
            st.info("No staff accounts found")
    
    with tab2:
        with st.form("staff_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Staff", "Manager"])
            
            st.subheader("Page Access Permissions")
            col1, col2 = st.columns(2)
            
            with col1:
                can_access_orders = st.checkbox("Orders", value=True)
                can_access_customers = st.checkbox("Customers", value=True)
                can_access_inventory = st.checkbox("Inventory", value=False)
            
            with col2:
                can_access_reports = st.checkbox("Reports", value=False)
                can_access_backup = st.checkbox("Backup", value=False)
            
            if st.form_submit_button("Save Staff Account"):
                # Check if username exists
                c = conn.cursor()
                c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                exists = c.fetchone()
                
                if exists and username == "admin":
                    st.error("Cannot modify admin account!")
                else:
                    hashed_pw = hash_password(password)
                    
                    if exists:
                        # Update existing user
                        conn.execute("""
                            UPDATE users SET 
                            password = ?,
                            role = ?,
                            can_access_orders = ?,
                            can_access_customers = ?,
                            can_access_inventory = ?,
                            can_access_reports = ?,
                            can_access_backup = ?
                            WHERE username = ?
                        """, (hashed_pw, role, can_access_orders, can_access_customers,
                              can_access_inventory, can_access_reports, can_access_backup, username))
                    else:
                        # Create new user
                        conn.execute("""
                            INSERT INTO users 
                            (username, password, role, can_access_orders, can_access_customers,
                             can_access_inventory, can_access_reports, can_access_backup)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (username, hashed_pw, role, can_access_orders, can_access_customers,
                              can_access_inventory, can_access_reports, can_access_backup))
                    
                    conn.commit()
                    st.success("Staff account saved successfully!")
                    st.rerun()

# ======================
# MAIN APP LAYOUT
# ======
