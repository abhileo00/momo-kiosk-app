import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import os
import ast

# Constants
DATA_DIR = "data/"
os.makedirs(DATA_DIR, exist_ok=True)

USERS_CSV = os.path.join(DATA_DIR, "users.csv")
ORDERS_CSV = os.path.join(DATA_DIR, "orders.csv")
CUSTOMERS_CSV = os.path.join(DATA_DIR, "customers.csv")
MENU_CSV = os.path.join(DATA_DIR, "menu.csv")

# Initialize all data files with proper columns if they don't exist
def initialize_data_files():
    default_data = {
        USERS_CSV: ['username', 'password', 'role', 'access_pages'],
        ORDERS_CSV: ['timestamp', 'customer', 'items', 'total', 'payment_mode', 'staff'],
        CUSTOMERS_CSV: ['name', 'phone', 'email', 'join_date'],
        MENU_CSV: ['category', 'item', 'price', 'cost', 'stock']
    }
    
    for file, columns in default_data.items():
        if not os.path.exists(file):
            pd.DataFrame(columns=columns).to_csv(file, index=False)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def safe_read_csv(file, default_columns):
    """Robust CSV reading that handles empty files and errors"""
    try:
        if os.path.exists(file) and os.path.getsize(file) > 0:
            df = pd.read_csv(file)
            # Ensure all expected columns exist
            for col in default_columns:
                if col not in df.columns:
                    df[col] = None
            return df
        return pd.DataFrame(columns=default_columns)
    except Exception as e:
        st.error(f"Error reading {file}: {str(e)}")
        return pd.DataFrame(columns=default_columns)

def save_csv(df, file):
    try:
        df.to_csv(file, index=False)
    except Exception as e:
        st.error(f"Error saving {file}: {str(e)}")

def authenticate(username, password):
    users_df = safe_read_csv(USERS_CSV, ['username', 'password', 'role', 'access_pages'])
    user = users_df[users_df['username'] == username]
    if not user.empty and user.iloc[0]['password'] == hash_password(password):
        return user.iloc[0]['role'], user.iloc[0]['access_pages'].split(',')
    return None, None

# Initialize data files
initialize_data_files()

# Create default admin if none exists
users_df = safe_read_csv(USERS_CSV, ['username', 'password', 'role', 'access_pages'])
if users_df.empty:
    save_csv(pd.DataFrame([{
        'username': 'admin',
        'password': hash_password('admin123'),
        'role': 'Admin',
        'access_pages': 'all'
    }]), USERS_CSV)

# Initialize session state
session_defaults = {
    'current_user': None,
    'user_role': None,
    'user_pages': [],
    'current_order': []
}

for key, default in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Login page
if not st.session_state.current_user:
    st.title("Food Hub - Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            role, pages = authenticate(username, password)
            if role:
                st.session_state.current_user = username
                st.session_state.user_role = role
                st.session_state.user_pages = pages if 'all' not in pages else ['Orders', 'Customers', 'Inventory', 'Reports', 'Manage']
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# Application Pages with robust error handling
def orders_page():
    st.header("Orders Management")
    menu_df = safe_read_csv(MENU_CSV, ['category', 'item', 'price', 'cost', 'stock'])
    
    if menu_df.empty:
        st.warning("No items in menu. Please add items to inventory first.")
        return

    # Order creation UI
    # ... (rest of orders page implementation)

def customers_page():
    st.header("Customers Management")
    customers_df = safe_read_csv(CUSTOMERS_CSV, ['name', 'phone', 'email', 'join_date'])
    
    # Customers UI
    # ... (rest of customers page implementation)

def inventory_page():
    st.header("Inventory Management")
    menu_df = safe_read_csv(MENU_CSV, ['category', 'item', 'price', 'cost', 'stock'])
    
    # Inventory UI
    # ... (rest of inventory page implementation)

def reports_page():
    st.header("Sales Reports")
    orders_df = safe_read_csv(ORDERS_CSV, ['timestamp', 'customer', 'items', 'total', 'payment_mode', 'staff'])
    
    if orders_df.empty:
        st.info("No orders yet. Place some orders to see reports.")
        return

    try:
        orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
        # Rest of reports processing
    except Exception as e:
        st.error(f"Error processing reports: {str(e)}")
        return

    # Reports UI
    # ... (rest of reports page implementation)

def manage_users_page():
    st.header("User Management")
    users_df = safe_read_csv(USERS_CSV, ['username', 'password', 'role', 'access_pages'])
    
    # User management UI
    # ... (rest of manage users page implementation)

# Main App Layout
st.title("Food Hub - Restaurant Management System")
st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")

# Define all available pages
PAGES = {
    "Orders": orders_page,
    "Customers": customers_page,
    "Inventory": inventory_page,
    "Reports": reports_page,
    "Manage": manage_users_page
}

# Navigation
if st.session_state.user_role == "Admin":
    visible_pages = list(PAGES.keys())
else:
    visible_pages = [p for p in st.session_state.user_pages if p in PAGES]

tabs = st.tabs(visible_pages)
for tab, page_name in zip(tabs, visible_pages):
    with tab:
        PAGES[page_name]()

# Logout
if st.sidebar.button("Logout", type="primary"):
    for key in session_defaults.keys():
        st.session_state.pop(key, None)
    st.rerun()
