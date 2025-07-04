import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import hashlib
import shutil
import os
import plotly.express as px
from pathlib import Path

# Database Configuration
DB_FILE = "food_hub.db"
BACKUP_DIR = "backups/"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Initialize database with enhanced schema
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables with improved schema
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  customer_id INTEGER,
                  items TEXT,
                  subtotal REAL,
                  tax REAL,
                  discount REAL,
                  total REAL,
                  payment_mode TEXT,
                  status TEXT DEFAULT 'Pending',
                  staff_id INTEGER,
                  notes TEXT,
                  FOREIGN KEY(customer_id) REFERENCES customers(id),
                  FOREIGN KEY(staff_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  phone TEXT UNIQUE,
                  email TEXT,
                  address TEXT,
                  credit_balance REAL DEFAULT 0,
                  total_orders INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0,
                  join_date TEXT,
                  last_order_date TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category TEXT,
                  item TEXT UNIQUE,
                  description TEXT,
                  price REAL,
                  cost REAL,
                  stock INTEGER,
                  min_stock INTEGER DEFAULT 5,
                  is_available INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  full_name TEXT,
                  role TEXT,
                  is_active INTEGER DEFAULT 1,
                  last_login TEXT)''')
    
    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)", 
                 ("admin", hash_password("admin123"), "System Administrator", "Admin"))
    
    # Create indexes for better performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_menu_category ON menu(category)")
    
    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT id, password, role FROM users WHERE username = ? AND is_active = 1", (username,))
    result = c.fetchone()
    if result and result[1] == hash_password(password):
        # Update last login
        c.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result[0]))
        conn.commit()
        return result[0], result[2]  # Return user_id and role
    return None, None

# Initialize database
conn = init_db()

# Session state management
def init_session_state():
    defaults = {
        'current_order': [],
        'current_customer': None,
        'current_user_id': None,
        'current_user_role': None,
        'current_user_name': None,
        'edit_item': None,
        'edit_customer': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Login Screen
if not st.session_state.current_user_id:
    st.title("Food Hub - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            user_id, role = authenticate(username, password)
            if user_id:
                st.session_state.current_user_id = user_id
                st.session_state.current_user_role = role
                # Get user full name
                c = conn.cursor()
                c.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
                result = c.fetchone()
                st.session_state.current_user_name = result[0] if result else username
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# ======================
# CORE FUNCTIONS
# ======================

def create_backup():
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_DIR}foodhub_backup_{timestamp}.db"
    shutil.copy2(DB_FILE, backup_file)
    return backup_file

def get_menu_items(category_filter=None, available_only=True):
    """Retrieve menu items with optional filters"""
    query = "SELECT * FROM menu"
    conditions = []
    params = []
    
    if available_only:
        conditions.append("is_available = 1")
    if category_filter:
        conditions.append("category = ?")
        params.append(category_filter)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    return pd.read_sql(query, conn, params=params if params else None)

def process_order(customer_id, items, payment_mode, notes=""):
    """Process and save an order to the database"""
    try:
        subtotal = sum(item['total'] for item in items)
        tax = subtotal * 0.1  # Example 10% tax
        total = subtotal + tax
        
        order_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": customer_id,
            "items": str(items),
            "subtotal": subtotal,
            "tax": tax,
            "discount": 0,  # Could be calculated based on customer loyalty
            "total": total,
            "payment_mode": payment_mode,
            "status": "Completed",
            "staff_id": st.session_state.current_user_id,
            "notes": notes
        }
        
        # Start transaction
        with conn:
            # Insert order
            order_df = pd.DataFrame([order_data])
            order_df.to_sql('orders', conn, if_exists='append', index=False)
            
            # Update inventory
            for item in items:
                conn.execute("UPDATE menu SET stock = stock - ? WHERE item = ?", 
                           (item['quantity'], item['item']))
            
            # Update customer stats if not walk-in
            if customer_id and customer_id > 0:
                conn.execute("""
                    UPDATE customers 
                    SET total_orders = total_orders + 1,
                        total_spent = total_spent + ?,
                        last_order_date = ?
                    WHERE id = ?
                """, (total, order_data['timestamp'], customer_id))
            
            # If credit payment, update balance
            if payment_mode == "Credit" and customer_id:
                conn.execute("""
                    UPDATE customers 
                    SET credit_balance = credit_balance + ?
                    WHERE id = ?
                """, (total, customer_id))
        
        return True
    except Exception as e:
        st.error(f"Error processing order: {str(e)}")
        conn.rollback()
        return False

# ======================
# TAB CONTENT FUNCTIONS
# ======================

def order_tab():
    st.header("New Order")
    
    # Customer Selection
    customers = pd.read_sql("SELECT id, name, phone FROM customers ORDER BY name", conn)
    customer_options = {0: "Walk-in Customer"}
    customer_options.update({row['id']: f"{row['name']} ({row['phone']})" for _, row in customers.iterrows()})
    
    selected_customer = st.selectbox(
        "Select Customer",
        options=list(customer_options.keys()),
        format_func=lambda x: customer_options[x]
    )
    
    # Add new customer on the fly
    with st.expander("Add New Customer"):
        with st.form("quick_customer_form"):
            name = st.text_input("Name")
            phone = st.text_input("Phone")
            if st.form_submit_button("Add Customer"):
                if name and phone:
                    try:
                        conn.execute(
                            "INSERT INTO customers (name, phone, join_date) VALUES (?, ?, ?)",
                            (name, phone, datetime.now().strftime("%Y-%m-%d"))
                        conn.commit()
                        st.success("Customer added!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Customer with this phone already exists")
    
    # Menu Selection
    menu_df = get_menu_items(available_only=True)
    categories = menu_df['category'].unique()
    
    category = st.selectbox("Menu Category", categories)
    items = menu_df[menu_df['category'] == category]
    
    # Display menu items in columns for better layout
    cols = st.columns(3)
    for idx, item in items.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"**{item['item']}** - ₹{item['price']}")
                st.caption(item.get('description', ''))
                st.write(f"Stock: {item['stock']}")
                
                qty = st.number_input(
                    "Quantity",
                    min_value=0,
                    max_value=item['stock'],
                    key=f"qty_{item['id']}",
                    label_visibility="collapsed"
                )
                
                if qty > 0 and st.button("Add to Order", key=f"add_{item['id']}"):
                    order_item = {
                        "item": item['item'],
                        "price": item['price'],
                        "quantity": qty,
                        "total": item['price'] * qty
                    }
                    st.session_state.current_order.append(order_item)
                    st.success(f"Added {qty} × {item['item']}")
                    time.sleep(0.3)
                    st.rerun()
    
    # Order Summary
    if st.session_state.current_order:
        st.subheader("Order Summary")
        order_df = pd.DataFrame(st.session_state.current_order)
        
        # Display order items with remove option
        for i, item in enumerate(st.session_state.current_order):
            cols = st.columns([3, 1, 1, 1])
            cols[0].write(f"{item['quantity']} × {item['item']}")
            cols[1].write(f"₹{item['price']}")
            cols[2].write(f"₹{item['total']}")
            if cols[3].button("❌", key=f"remove_{i}"):
                st.session_state.current_order.pop(i)
                st.rerun()
        
        subtotal = order_df['total'].sum()
        tax = subtotal * 0.1
        total = subtotal + tax
        
        st.markdown(f"""
        **Subtotal:** ₹{subtotal:.2f}  
        **Tax (10%):** ₹{tax:.2f}  
        **Total:** ₹{total:.2f}
        """)
        
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online", "Card"])
        notes = st.text_area("Order Notes")
        
        if st.button("Submit Order", type="primary"):
            if payment_mode == "Credit" and selected_customer == 0:
                st.error("Credit payment requires selecting a customer")
            else:
                if process_order(selected_customer if selected_customer != 0 else None, 
                               st.session_state.current_order, 
                               payment_mode,
                               notes):
                    st.success("Order submitted successfully!")
                    st.session_state.current_order = []
                    time.sleep(1)
                    st.rerun()

def customers_tab():
    st.header("Customer Management")
    
    tab1, tab2 = st.tabs(["Customer Directory", "Customer Details"])
    
    with tab1:
        st.subheader("All Customers")
        
        # Customer search and filters
        col1, col2 = st.columns(2)
        with col1:
            search_query = st.text_input("Search by name or phone")
        with col2:
            show_inactive = st.checkbox("Show inactive customers")
        
        # Build query
        query = "SELECT * FROM customers"
        conditions = []
        params = []
        
        if search_query:
            conditions.append("(name LIKE ? OR phone LIKE ?)")
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        if not show_inactive:
            conditions.append("is_active = 1")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY name"
        
        customers = pd.read_sql(query, conn, params=params)
        
        if not customers.empty:
            # Display customer table with action buttons
            for _, customer in customers.iterrows():
                with st.expander(f"{customer['name']} - {customer['phone']}"):
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].write(f"**Orders:** {customer['total_orders']}")
                    cols[1].write(f"**Spent:** ₹{customer['total_spent']:.2f}")
                    cols[2].write(f"**Credit:** ₹{customer['credit_balance']:.2f}")
                    if cols[3].button("Edit", key=f"edit_{customer['id']}"):
                        st.session_state.edit_customer = customer['id']
                        st.rerun()
        else:
            st.info("No customers found")
    
    with tab2:
        if st.session_state.edit_customer:
            # Edit existing customer
            customer = pd.read_sql(
                "SELECT * FROM customers WHERE id = ?", 
                conn, 
                params=(st.session_state.edit_customer,)
            ).iloc[0]
            
            st.subheader(f"Editing: {customer['name']}")
        else:
            # Add new customer
            st.subheader("Add New Customer")
            customer = None
        
        with st.form("customer_form"):
            name = st.text_input("Full Name", value=customer['name'] if customer else "")
            phone = st.text_input("Phone Number", value=customer['phone'] if customer else "")
            email = st.text_input("Email", value=customer['email'] if customer else "")
            address = st.text_area("Address", value=customer['address'] if customer else "")
            credit = st.number_input("Credit Balance", 
                                    min_value=0.0, 
                                    value=float(customer['credit_balance']) if customer else 0.0)
            is_active = st.checkbox("Active", value=bool(customer['is_active']) if customer else True)
            
            if st.form_submit_button("Save Customer"):
                if not name or not phone:
                    st.error("Name and phone are required")
                else:
                    try:
                        if customer is not None:
                            # Update existing customer
                            conn.execute("""
                                UPDATE customers SET
                                    name = ?,
                                    phone = ?,
                                    email = ?,
                                    address = ?,
                                    credit_balance = ?,
                                    is_active = ?
                                WHERE id = ?
                            """, (name, phone, email, address, credit, int(is_active), customer['id']))
                        else:
                            # Insert new customer
                            conn.execute("""
                                INSERT INTO customers 
                                (name, phone, email, address, credit_balance, join_date, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (name, phone, email, address, credit, datetime.now().strftime("%Y-%m-%d"), int(is_active)))
                        
                        conn.commit()
                        st.session_state.edit_customer = None
                        st.success("Customer saved successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("A customer with this phone number already exists")

def inventory_tab():
    st.header("Inventory Management")
    
    tab1, tab2 = st.tabs(["Current Inventory", "Add/Edit Items"])
    
    with tab1:
        st.subheader("Inventory Status")
        
        # Low stock warning
        low_stock = pd.read_sql(
            "SELECT * FROM menu WHERE stock <= min_stock ORDER BY stock ASC", 
            conn
        )
        if not low_stock.empty:
            st.warning(f"{len(low_stock)} items below minimum stock level")
            for _, item in low_stock.iterrows():
                st.write(f"⚠️ {item['item']} - Only {item['stock']} left (min: {item['min_stock']})")
        
        # Full inventory display
        inventory = pd.read_sql("SELECT * FROM menu ORDER BY category, item", conn)
        st.dataframe(
            inventory,
            column_config={
                "price": st.column_config.NumberColumn("Price", format="₹%.2f"),
                "cost": st.column_config.NumberColumn("Cost", format="₹%.2f"),
                "stock": st.column_config.NumberColumn("Stock", min_value=0),
                "min_stock": st.column_config.NumberColumn("Min Stock", min_value=0),
                "is_available": st.column_config.CheckboxColumn("Available")
            },
            hide_index=True,
            use_container_width=True
        )
    
    with tab2:
        if st.session_state.edit_item:
            # Edit existing item
            item = pd.read_sql(
                "SELECT * FROM menu WHERE id = ?", 
                conn, 
                params=(st.session_state.edit_item,)
            ).iloc[0]
            
            st.subheader(f"Editing: {item['item']}")
        else:
            # Add new item
            st.subheader("Add New Menu Item")
            item = None
        
        with st.form("item_form"):
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox(
                    "Category",
                    ["Appetizers", "Main Course", "Sides", "Desserts", "Beverages"],
                    index=0 if not item else ["Appetizers", "Main Course", "Sides", "Desserts", "Beverages"].index(item['category'])
                )
                item_name = st.text_input("Item Name", value=item['item'] if item else "")
                description = st.text_area("Description", value=item['description'] if item else "")
            with col2:
                price = st.number_input("Price (₹)", min_value=0.0, step=0.5, value=item['price'] if item else 0.0)
                cost = st.number_input("Cost (₹)", min_value=0.0, step=0.5, value=item['cost'] if item else 0.0)
                stock = st.number_input("Stock", min_value=0, value=item['stock'] if item else 0)
                min_stock = st.number_input("Minimum Stock", min_value=0, value=item['min_stock'] if item else 5)
            
            is_available = st.checkbox("Available", value=bool(item['is_
