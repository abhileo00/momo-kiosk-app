import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import hashlib
import shutil
import os
import matplotlib.pyplot as plt
import plotly.express as px
from PIL import Image
import base64

# ======================
# SYSTEM CONFIGURATION
# ======================
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"
IMAGE_DIR = "menu_images/"
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# Initialize database with sample data
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  customer_id INTEGER,
                  items TEXT,
                  total REAL,
                  payment_mode TEXT,
                  status TEXT DEFAULT 'Pending',
                  staff TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  phone TEXT UNIQUE,
                  credit_balance REAL DEFAULT 0,
                  total_orders INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0,
                  last_order TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category TEXT,
                  item TEXT UNIQUE,
                  description TEXT,
                  price REAL,
                  cost REAL,
                  stock INTEGER,
                  prep_time INTEGER,  # in minutes
                  image_path TEXT,
                  is_featured BOOLEAN DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  role TEXT,
                  pin TEXT)''')
    
    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, pin) VALUES (?, ?, ?, ?)", 
                 ("admin", hash_password("admin123"), "Admin", "1234"))
    
    # Insert sample menu items if empty
    c.execute("SELECT 1 FROM menu LIMIT 1")
    if not c.fetchone():
        sample_menu = [
            ("Momos", "Veg Momos (6 pcs)", "Steamed dumplings with vegetable filling", 80, 20, 100, 10, None, 1),
            ("Momos", "Chicken Momos (6 pcs)", "Steamed dumplings with chicken filling", 100, 30, 80, 10, None, 1),
            ("Sandwich", "Veg Club Sandwich", "Three layers with veggies and sauces", 120, 40, 50, 5, None, 1),
            ("Beverages", "Masala Chai", "Traditional spiced tea", 30, 10, 200, 2, None, 1)
        ]
        c.executemany("INSERT INTO menu (category, item, description, price, cost, stock, prep_time, image_path, is_featured) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_menu)
    
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

# Session state
if 'current_order' not in st.session_state:
    st.session_state.current_order = []
if 'current_customer' not in st.session_state:
    st.session_state.current_customer = None
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'kiosk_mode' not in st.session_state:
    st.session_state.kiosk_mode = False

# ======================
# CORE FUNCTIONS
# ======================

def get_menu_items(category=None, featured=False):
    query = "SELECT * FROM menu WHERE stock > 0"
    if category:
        query += f" AND category = '{category}'"
    if featured:
        query += " AND is_featured = 1"
    return pd.read_sql(query, conn)

def get_customer_by_phone(phone):
    return pd.read_sql(f"SELECT * FROM customers WHERE phone = '{phone}'", conn)

def save_order(order_data):
    order_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_df = pd.DataFrame([order_data])
    order_df.to_sql('orders', conn, if_exists='append', index=False)
    
    # Update customer stats if not walk-in
    if order_data['customer_id']:
        conn.execute(f"""
            UPDATE customers 
            SET total_orders = total_orders + 1,
                total_spent = total_spent + {order_data['total']},
                last_order = '{order_data['timestamp']}'
            WHERE id = {order_data['customer_id']}
        """)
        conn.commit()

def update_stock(item_id, qty_change):
    conn.execute(f"UPDATE menu SET stock = stock + {qty_change} WHERE id = {item_id}")
    conn.commit()

# ======================
# KIOSK INTERFACE COMPONENTS
# ======================

def menu_item_card(item, show_add_button=True):
    with st.container():
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Display image if available
            if item['image_path'] and os.path.exists(item['image_path']):
                st.image(item['image_path'], width=150)
            else:
                st.image("https://via.placeholder.com/150", width=150)
        
        with col2:
            st.markdown(f"**{item['item']}**")
            st.markdown(f"₹{item['price']}")
            st.caption(item['description'])
            
            if item['stock'] < 10:
                st.warning(f"Only {item['stock'] left!")
            
            if show_add_button:
                qty = st.number_input(
                    "Qty",
                    min_value=1,
                    max_value=min(10, item['stock']),
                    key=f"qty_{item['id']}",
                    value=1
                )
                
                if st.button("Add to Order", key=f"add_{item['id']}"):
                    order_item = {
                        "id": item['id'],
                        "name": item['item'],
                        "price": item['price'],
                        "qty": qty,
                        "total": item['price'] * qty
                    }
                    st.session_state.current_order.append(order_item)
                    update_stock(item['id'], -qty)
                    st.success(f"Added {qty} × {item['item']}")
                    time.sleep(0.3)
                    st.rerun()

def order_summary_panel():
    if not st.session_state.current_order:
        return
    
    st.subheader("Your Order")
    
    for i, item in enumerate(st.session_state.current_order):
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(f"{item['name']} × {item['qty']}")
        with cols[1]:
            st.markdown(f"₹{item['total']}")
        with cols[2]:
            if st.button("❌", key=f"remove_{i}"):
                st.session_state.current_order.pop(i)
                update_stock(item['id'], item['qty'])
                st.rerun()
    
    total = sum(item['total'] for item in st.session_state.current_order)
    st.markdown(f"**Total: ₹{total}**")
    
    # Payment options
    if st.session_state.current_customer:
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online"])
    else:
        payment_mode = st.radio("Payment Method", ["Cash", "Online"])
    
    if st.button("Place Order", type="primary"):
        if payment_mode == "Credit" and not st.session_state.current_customer:
            st.error("Please register or identify customer for credit payment")
        else:
            order_data = {
                "customer_id": st.session_state.current_customer['id'] if st.session_state.current_customer else None,
                "items": str(st.session_state.current_order),
                "total": total,
                "payment_mode": payment_mode,
                "status": "Completed",
                "staff": st.session_state.current_user
            }
            
            save_order(order_data)
            
            if payment_mode == "Credit" and st.session_state.current_customer:
                # Update customer credit
                conn.execute(f"""
                    UPDATE customers 
                    SET credit_balance = credit_balance + {total}
                    WHERE id = {st.session_state.current_customer['id']}
                """)
                conn.commit()
            
            st.success("Order placed successfully!")
            st.session_state.current_order = []
            time.sleep(1)
            st.rerun()

# ======================
# TAB CONTENT FUNCTIONS
# ======================

def kiosk_tab():
    st.header("Self-Service Kiosk")
    
    # Customer identification
    with st.expander("Customer Info", expanded=True):
        phone = st.text_input("Enter Phone Number (optional)", key="customer_phone")
        
        if phone:
            customer = get_customer_by_phone(phone)
            if not customer.empty:
                st.session_state.current_customer = customer.iloc[0].to_dict()
                st.success(f"Welcome back, {st.session_state.current_customer['name']}!")
                st.markdown(f"**Credit Balance:** ₹{st.session_state.current_customer['credit_balance']}")
            elif st.button("Register New Customer"):
                register_customer(phone)
    
    # Featured items
    st.subheader("Featured Items")
    featured_items = get_menu_items(featured=True)
    if not featured_items.empty:
        cols = st.columns(3)
        for i, (_, item) in enumerate(featured_items.iterrows()):
            with cols[i % 3]:
                menu_item_card(item)
    
    # Menu categories
    categories = pd.read_sql("SELECT DISTINCT category FROM menu WHERE stock > 0", conn)['category'].tolist()
    
    for category in categories:
        st.subheader(category)
        items = get_menu_items(category)
        
        cols = st.columns(3)
        for i, (_, item) in enumerate(items.iterrows()):
            with cols[i % 3]:
                menu_item_card(item)
    
    # Order summary always visible at bottom
    order_summary_panel()

def orders_tab():
    st.header("Order Management")
    
    tab1, tab2 = st.tabs(["Current Orders", "Order History"])
    
    with tab1:
        st.subheader("Pending Orders")
        pending_orders = pd.read_sql("SELECT * FROM orders WHERE status = 'Pending'", conn)
        
        if not pending_orders.empty:
            for _, order in pending_orders.iterrows():
                with st.expander(f"Order #{order['id']} - {order['timestamp']}"):
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.markdown(f"**Customer:** {order['customer_id'] or 'Walk-in'}")
                        st.markdown(f"**Items:** {order['items']}")
                    with cols[1]:
                        st.markdown(f"**Total:** ₹{order['total']}")
                    with cols[2]:
                        if st.button("Mark Complete", key=f"complete_{order['id']}"):
                            conn.execute(f"UPDATE orders SET status = 'Completed' WHERE id = {order['id']}")
                            conn.commit()
                            st.rerun()
        else:
            st.info("No pending orders")
    
    with tab2:
        st.subheader("Order History")
        
        time_filter = st.selectbox("Filter by", ["Today", "This Week", "This Month", "All"])
        
        query = "SELECT * FROM orders WHERE status = 'Completed'"
        if time_filter == "Today":
            query += f" AND date(timestamp) = date('now')"
        elif time_filter == "This Week":
            query += f" AND date(timestamp) >= date('now', 'weekday 0', '-7 days')"
        elif time_filter == "This Month":
            query += f" AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')"
        
        orders = pd.read_sql(query, conn)
        
        if not orders.empty:
            st.dataframe(orders)
            
            # Sales chart
            orders['timestamp'] = pd.to_datetime(orders['timestamp'])
            daily_sales = orders.groupby(orders['timestamp'].dt.date)['total'].sum().reset_index()
            
            fig = px.bar(daily_sales, x='timestamp', y='total', 
                         title="Daily Sales Trend", labels={'total': 'Total Sales (₹)'})
            st.plotly_chart(fig)
        else:
            st.info("No orders found")

def customers_tab():
    st.header("Customer Management")
    
    tab1, tab2, tab3 = st.tabs(["Customer List", "Credit Management", "New Customer"])
    
    with tab1:
        st.subheader("All Customers")
        customers = pd.read_sql("SELECT * FROM customers", conn)
        
        if not customers.empty:
            st.dataframe(customers)
        else:
            st.info("No customers found")
    
    with tab2:
        st.subheader("Credit Accounts")
        
        customer = st.selectbox(
            "Select Customer",
            pd.read_sql("SELECT id, name, phone FROM customers", conn).apply(
                lambda x: f"{x['name']} ({x['phone']}) - ID: {x['id']}", axis=1
            )
        )
        
        if customer:
            customer_id = int(customer.split("ID: ")[1])
            customer_data = pd.read_sql(f"SELECT * FROM customers WHERE id = {customer_id}", conn).iloc[0]
            
            st.markdown(f"""
            **Current Balance:** ₹{customer_data['credit_balance']}  
            **Total Orders:** {customer_data['total_orders']}  
            **Total Spent:** ₹{customer_data['total_spent']}
            """)
            
            amount = st.number_input("Amount", min_value=0.0)
            if st.button("Add Credit"):
                conn.execute(f"""
                    UPDATE customers 
                    SET credit_balance = credit_balance + {amount}
                    WHERE id = {customer_id}
                """)
                conn.commit()
                st.success("Credit added!")
                st.rerun()
    
    with tab3:
        st.subheader("Register New Customer")
        
        with st.form("new_customer_form"):
            name = st.text_input("Full Name")
            phone = st.text_input("Phone Number")
            initial_credit = st.number_input("Initial Credit", min_value=0.0, value=0.0)
            
            if st.form_submit_button("Register Customer"):
                try:
                    conn.execute("""
                        INSERT INTO customers 
                        (name, phone, credit_balance) 
                        VALUES (?, ?, ?)
                    """, (name, phone, initial_credit))
                    conn.commit()
                    st.success("Customer registered successfully!")
                except sqlite3.IntegrityError:
                    st.error("Phone number already exists")

def menu_management_tab():
    st.header("Menu Management")
    
    tab1, tab2 = st.tabs(["Current Menu", "Add New Item"])
    
    with tab1:
        st.subheader("Edit Menu Items")
        menu_items = pd.read_sql("SELECT * FROM menu", conn)
        
        edited_items = st.data_editor(
            menu_items,
            column_config={
                "price": st.column_config.NumberColumn("Price", min_value=0),
                "cost": st.column_config.NumberColumn("Cost", min_value=0),
                "stock": st.column_config.NumberColumn("Stock", min_value=0),
                "is_featured": st.column_config.CheckboxColumn("Featured"),
                "image_path": st.column_config.ImageColumn("Image")
            },
            num_rows="dynamic",
            key="menu_editor"
        )
        
        if st.button("Save Changes"):
            edited_items.to_sql('menu', conn, if_exists='replace', index=False)
            st.success("Menu updated!")
    
    with tab2:
        st.subheader("Add New Menu Item")
        
        with st.form("new_item_form"):
            category = st.text_input("Category")
            item = st.text_input("Item Name")
            description = st.text_area("Description")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Initial Stock", min_value=0)
            prep_time = st.number_input("Preparation Time (minutes)", min_value=1)
            is_featured = st.checkbox("Featured Item")
            image_file = st.file_uploader("Item Image", type=["jpg", "png"])
            
            if st.form_submit_button("Add Item"):
                image_path = None
                if image_file:
                    image_path = os.path.join(IMAGE_DIR, f"{item.replace(' ', '_')}.jpg")
                    with open(image_path, "wb") as f:
                        f.write(image_file.getbuffer())
                
                conn.execute("""
                    INSERT INTO menu 
                    (category, item, description, price, cost, stock, prep_time, image_path, is_featured)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (category, item, description, price, cost, stock, prep_time, image_path, is_featured))
                conn.commit()
                st.success("Item added to menu!")
                st.rerun()

def reports_tab():
    st.header("Sales Reports")
    
    tab1, tab2, tab3 = st.tabs(["Sales Analysis", "Customer Insights", "Inventory Reports"])
    
    with tab1:
        st.subheader("Sales Performance")
        
        time_frame = st.selectbox("Time Period", ["Today", "This Week", "This Month", "Custom Range"])
        
        if time_frame == "Custom Range":
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date")
            with col2:
                end_date = st.date_input("End Date")
            query = f"SELECT * FROM orders WHERE date(timestamp) BETWEEN '{start_date}' AND '{end_date}'"
        else:
            if time_frame == "Today":
                query = "SELECT * FROM orders WHERE date(timestamp) = date('now')"
            elif time_frame == "This Week":
                query = "SELECT * FROM orders WHERE date(timestamp) >= date('now', 'weekday 0', '-7 days')"
            elif time_frame == "This Month":
                query = "SELECT * FROM orders WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')"
        
        orders = pd.read_sql(query, conn)
        
        if not orders.empty:
            # Sales metrics
            total_sales = orders['total'].sum()
            avg_order = orders['total'].mean()
            order_count = len(orders)
            
            cols = st.columns(3)
            cols[0].metric("Total Sales", f"₹{total_sales:,.2f}")
            cols[1].metric("Average Order", f"₹{avg_order:,.2f}")
            cols[2].metric("Total Orders", order_count)
            
            # Sales by payment method
            st.subheader("Sales by Payment Method")
            payment_stats = orders.groupby('payment_mode')['total'].agg(['sum', 'count'])
            fig1 = px.pie(payment_stats, values='sum', names=payment_stats.index, title="Revenue by Payment Method")
            st.plotly_chart(fig1)
            
            # Daily sales trend
            st.subheader("Daily Sales Trend")
            orders['date'] = pd.to_datetime(orders['timestamp']).dt.date
            daily_sales = orders.groupby('date')['total'].sum().reset_index()
            fig2 = px.line(daily_sales, x='date', y='total', title="Daily
