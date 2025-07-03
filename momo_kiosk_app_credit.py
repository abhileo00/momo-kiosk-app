import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import shutil
import re

# ======================
# DATA CONFIGURATION
# ======================
DATA_FOLDER = "food_snacks_data/"
DATABASES = {
    "orders": DATA_FOLDER + "orders.csv",
    "menu": DATA_FOLDER + "menu.csv",
    "customers": DATA_FOLDER + "customers.csv",
    "credit": DATA_FOLDER + "credit_transactions.csv",
    "inventory": DATA_FOLDER + "inventory.csv"
}

TOPPINGS = {
    "Extra Cheese": 20,
    "Masala": 10,
    "Butter": 10,
    "Egg": 15
}

CUSTOMER_COLUMNS = [
    "mobile", "name", "credit_balance", "total_spent",
    "order_count", "first_order", "last_order", "loyalty_points"
]

MENU_ITEMS = {
    "Veg Momo": {"price": 80, "category": "Steamed"},
    "Chicken Momo": {"price": 100, "category": "Steamed"},
    "Fried Momo": {"price": 120, "category": "Fried"},
    "Jhol Momo": {"price": 110, "category": "Soup"},
    "Chilli Momo": {"price": 130, "category": "Fried"},
    "Paneer Momo": {"price": 90, "category": "Steamed"},
    "French Fries": {"price": 60, "category": "Snacks"},
    "Burger": {"price": 90, "category": "Snacks"},
    "Sandwich": {"price": 70, "category": "Snacks"}
}

# ======================
# DATA MANAGEMENT
# ======================
def init_data_system():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        os.makedirs(DATA_FOLDER + "backups/")

    # Initialize all databases
    for db_name, db_path in DATABASES.items():
        if not os.path.exists(db_path):
            if db_name == "menu":
                menu_df = pd.DataFrame.from_dict(MENU_ITEMS, orient='index').reset_index()
                menu_df = menu_df.rename(columns={'index': 'item'})
                menu_df.to_csv(db_path, index=False)
            else:
                pd.DataFrame().to_csv(db_path, index=False)

def load_db(db_name):
    try:
        return pd.read_csv(DATABASES[db_name])
    except:
        return pd.DataFrame()

def save_db(db_name, df):
    df.to_csv(DATABASES[db_name], index=False)

def get_customer(mobile):
    customers_df = load_db("customers")
    if not customers_df.empty and mobile in customers_df['mobile'].values:
        return customers_df[customers_df['mobile'] == mobile].iloc[0].to_dict()
    return None

def update_customer(mobile, name=None, amount=0, order_placed=False):
    customers_df = load_db("customers")
    
    if not customers_df.empty and mobile in customers_df['mobile'].values:
        idx = customers_df[customers_df['mobile'] == mobile].index[0]
        
        if order_placed:
            customers_df.at[idx, 'order_count'] += 1
            customers_df.at[idx, 'total_spent'] += amount
            customers_df.at[idx, 'last_order'] = datetime.now().strftime('%Y-%m-%d')
            customers_df.at[idx, 'loyalty_points'] += int(amount / 10)
            
        if name:
            customers_df.at[idx, 'name'] = name
    else:
        new_customer = {
            "mobile": mobile,
            "name": name if name else "New Customer",
            "credit_balance": 0,
            "total_spent": amount if order_placed else 0,
            "order_count": 1 if order_placed else 0,
            "first_order": datetime.now().strftime('%Y-%m-%d') if order_placed else "",
            "last_order": datetime.now().strftime('%Y-%m-%d') if order_placed else "",
            "loyalty_points": int(amount / 10) if order_placed else 0
        }
        customers_df = pd.concat([customers_df, pd.DataFrame([new_customer])], ignore_index=True)
    
    save_db("customers", customers_df)

def calculate_total(order_items):
    total = 0
    for item in order_items:
        total += item['price'] * item['quantity']
        for topping in item.get('toppings', []):
            total += TOPPINGS.get(topping, 0) * item['quantity']
    return total

def create_backup():
    backup_folder = DATA_FOLDER + "backups/" + datetime.now().strftime("%Y%m%d_%H%M%S") + "/"
    os.makedirs(backup_folder)
    for db_file in DATABASES.values():
        if os.path.exists(db_file):
            shutil.copy2(db_file, backup_folder)
    return backup_folder

# ======================
# STREAMLIT APP
# ======================
st.set_page_config(page_title="Food and Snacks", layout="wide")
init_data_system()

# Initialize session state
if "user_role" not in st.session_state:
    st.session_state.user_role = None
    st.session_state.authenticated = False
    st.session_state.username = None

if "current_order" not in st.session_state:
    st.session_state.current_order = {
        "items": [],
        "customer_mobile": "",
        "customer_name": "",
        "payment_method": "Cash",
        "paid": False
    }

# Authentication credentials
VALID_USERS = {
    "staff": {
        "password": "staff123",
        "role": "Staff"
    },
    "admin": {
        "password": "admin123",
        "role": "Admin"
    }
}

# Login Page
if not st.session_state.authenticated:
    st.title("Food and Snacks - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username").lower()
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if username in VALID_USERS:
                if password == VALID_USERS[username]["password"]:
                    st.session_state.user_role = VALID_USERS[username]["role"]
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Incorrect password")
            else:
                st.error("Invalid username")
    st.stop()

# Main App
st.sidebar.title(f"Welcome, {st.session_state.username} ({st.session_state.user_role})")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

# Tabs setup based on role
tabs = ["📝 Order", "👥 Customers"]
if st.session_state.user_role == "Admin":
    tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])

selected_tab = st.tabs(tabs)

# [Rest of the code remains exactly the same as in the previous version]
# [Only the app name references have been changed from "Momo Kiosk Pro" to "Food and Snacks"]
