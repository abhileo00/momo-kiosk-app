import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import hashlib
import os
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns

# ======================
# SYSTEM CONFIGURATION
# ======================
st.set_page_config(
    page_title="Food Order Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
def init_db():
    conn = sqlite3.connect('food_orders.db')
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  customer TEXT,
                  category TEXT,
                  item TEXT,
                  qty INTEGER,
                  toppings TEXT,
                  total_sale REAL,
                  total_cost REAL,
                  profit REAL,
                  payment_mode TEXT,
                  status TEXT DEFAULT 'pending',
                  staff TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  phone TEXT,
                  email TEXT,
                  credit_balance REAL DEFAULT 0,
                  total_orders INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0,
                  last_order TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category TEXT,
                  item TEXT UNIQUE,
                  price REAL,
                  cost REAL,
                  active BOOLEAN DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item TEXT UNIQUE,
                  current_stock INTEGER,
                  alert_threshold INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  role TEXT,
                  active BOOLEAN DEFAULT 1)''')
    
    conn.commit()
    return conn

conn = init_db()

# ======================
# AUTHENTICATION SYSTEM
# ======================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT password, role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and result[0] == hash_password(password):
        return result[1]  # Return role
    return None

# ======================
# DATA MANAGEMENT
# ======================
def get_menu_items(category=None):
    query = "SELECT * FROM menu WHERE active = 1"
    if category:
        query += f" AND category = '{category}'"
    return pd.read_sql(query, conn)

def get_customer(name):
    return pd.read_sql(f"SELECT * FROM customers WHERE name = '{name}'", conn)

def save_order(order_data):
    order_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_df = pd.DataFrame([order_data])
    order_df.to_sql('orders', conn, if_exists='append', index=False)
    
    # Update customer stats
    if order_data['customer'] != "Walk-in":
        conn.execute(f"""
            UPDATE customers 
            SET total_orders = total_orders + 1,
                total_spent = total_spent + {order_data['total_sale']},
                last_order = '{order_data['timestamp']}'
            WHERE name = '{order_data['customer']}'
        """)
        conn.commit()

def update_inventory(item, qty_change):
    conn.execute(f"""
        UPDATE inventory 
        SET current_stock = current_stock + {qty_change}
        WHERE item = '{item}'
    """)
    conn.commit()

# ======================
# UI COMPONENTS
# ======================
def menu_item_card(item, details):
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{item}**")
            st.markdown(f"Price: ₹{details['price']}")
            
            if details.get('current_stock', 0) <= details.get('alert_threshold', 0):
                st.warning(f"Low stock: {details['current_stock']} remaining")
            
        with col2:
            qty = st.number_input(
                "Qty",
                min_value=0,
                max_value=min(20, details.get('current_stock', 20)),
                key=f"qty_{item}",
                value=0
            )
            
        if qty > 0:
            toppings = []
            if st.checkbox("Add toppings", key=f"top_toggle_{item}"):
                cols = st.columns(4)
                for i, (top_name, top_price) in enumerate(TOPPINGS.items()):
                    with cols[i % 4]:
                        if st.checkbox(f"{top_name} (+₹{top_price})", key=f"top_{item}_{top_name}"):
                            toppings.append((top_name, top_price))
            
            if st.button("Add to Order", key=f"btn_{item}"):
                topping_names = ", ".join([t[0] for t in toppings])
                total_price = (details["price"] + sum([t[1] for t in toppings])) * qty
                
                order_data = {
                    "customer": st.session_state.customer_name,
                    "category": details["category"],
                    "item": item,
                    "qty": qty,
                    "toppings": topping_names,
                    "total_sale": total_price,
                    "total_cost": details["cost"] * qty,
                    "profit": total_price - (details["cost"] * qty),
                    "payment_mode": "Pending",
                    "staff": st.session_state.current_user
                }
                
                st.session_state.current_order.append(order_data)
                update_inventory(item, -qty)
                st.success(f"Added {qty} × {item}")
                time.sleep(0.3)
                st.rerun()

# ======================
# MAIN APPLICATION
# ======================
def main():
    # Initialize session state
    if 'current_order' not in st.session_state:
        st.session_state.current_order = []
    if 'customer_name' not in st.session_state:
        st.session_state.customer_name = "Walk-in"
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
        return
    
    # Main Application
    st.title("Food Order Pro")
    st.markdown(f"**Logged in as:** {st.session_state.current_user} ({st.session_state.user_role})")
    
    # Navigation
    menu_items = {
        "New Order": new_order,
        "Order History": order_history,
        "Customer Management": customer_management,
        "Menu Management": menu_management,
        "Inventory": inventory_management,
        "Reports": reports,
        "Admin": admin_panel
    }
    
    if st.session_state.user_role == "Staff":
        menu_items = {k: v for k, v in menu_items.items() if k in ["New Order", "Order History"]}
    
    selected = st.sidebar.radio("Navigation", list(menu_items.keys()))
    menu_items[selected]()

def new_order():
    st.header("New Order")
    
    # Customer Section
    with st.expander("Customer Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input(
                "Customer Name",
                value=st.session_state.customer_name,
                placeholder="Enter name or 'Walk-in'"
            )
            st.session_state.customer_name = customer_name
        
        with col2:
            if customer_name != "Walk-in":
                customer = get_customer(customer_name)
                if not customer.empty:
                    st.markdown(f"""
                    **Customer Info**  
                    Phone: {customer.iloc[0]['phone'] or 'N/A'}  
                    Email: {customer.iloc[0]['email'] or 'N/A'}  
                    Orders: {customer.iloc[0]['total_orders']}  
                    Total Spent: ₹{customer.iloc[0]['total_spent']}
                    """)
                elif st.button("Register New Customer"):
                    register_customer(customer_name)
                    st.rerun()

    # Menu Selection
    category = st.selectbox("Select Category", ["Momos", "Sandwich", "Maggi"])
    menu_df = get_menu_items(category)
    
    if menu_df.empty:
        st.warning("No items available in this category")
        return
    
    # Merge with inventory data
    inventory_df = pd.read_sql("SELECT item, current_stock, alert_threshold FROM inventory", conn)
    menu_df = menu_df.merge(inventory_df, on="item", how="left")
    
    # Display menu items
    for _, row in menu_df.iterrows():
        menu_item_card(row['item'], row.to_dict())

    # Order Summary
    if st.session_state.current_order:
        st.header("Order Summary")
        
        for item in st.session_state.current_order:
            with st.container():
                st.markdown(f"""
                **{item['item']}** × {item['qty']}  
                {f"Toppings: {item['toppings']}" if item['toppings'] else ""}  
                Price: ₹{item['total_sale']}
                """)
        
        total = sum(item['total_sale'] for item in st.session_state.current_order)
        st.subheader(f"Total: ₹{total}")
        
        # Payment and Submission
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online"])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Submit Order", type="primary"):
                for item in st.session_state.current_order:
                    item['payment_mode'] = payment_mode
                    save_order(item)
                
                st.success("Order submitted successfully!")
                st.session_state.current_order = []
                time.sleep(1)
                st.rerun()
        
        with col2:
            if st.button("Clear Order"):
                # Restore inventory
                for item in st.session_state.current_order:
                    update_inventory(item['item'], item['qty'])
                
                st.session_state.current_order = []
                st.rerun()

# Additional functions (order_history, customer_management, etc.) would be defined here
# with similar detailed implementations...

if __name__ == "__main__":
    main()
