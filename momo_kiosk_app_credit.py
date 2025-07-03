import streamlit as st
import pandas as pd
from datetime import datetime
import os
import shutil
import time

# ======================
# CONFIGURATION
# ======================
APP_NAME = "Food Hub"
DATA_FOLDER = "food_hub_data/"
BACKUP_FOLDER = os.path.join(DATA_FOLDER, "backups")
PASSWORDS = {"Admin": "admin123", "Staff": "staff123"}

DATABASES = {
    "orders": os.path.join(DATA_FOLDER, "orders.csv"),
    "menu": os.path.join(DATA_FOLDER, "menu.csv"),
    "customers": os.path.join(DATA_FOLDER, "customers.csv"),
    "credit": os.path.join(DATA_FOLDER, "credit_transactions.csv"),
    "inventory": os.path.join(DATA_FOLDER, "inventory.csv")
}

CUSTOMER_COLUMNS = ["mobile", "name", "credit_balance", "total_spent", "order_count", "first_order", "last_order", "loyalty_points"]

# ======================
# INITIALIZATION
# ======================
def init_data():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(BACKUP_FOLDER, exist_ok=True)

    if not os.path.exists(DATABASES["customers"]):
        pd.DataFrame(columns=CUSTOMER_COLUMNS).to_csv(DATABASES["customers"], index=False)

    if not os.path.exists(DATABASES["orders"]):
        pd.DataFrame(columns=["order_id", "mobile", "items", "total", "payment_method", "paid", "timestamp", "staff", "status"]).to_csv(DATABASES["orders"], index=False)

    if not os.path.exists(DATABASES["menu"]):
        default_menu = pd.DataFrame([
            {"category": "Thali", "item": "Veg Thali", "price": 70, "cost": 40},
            {"category": "Thali", "item": "Non-Veg Thali", "price": 100, "cost": 60},
            {"category": "Beverages", "item": "Tea (Small)", "price": 10, "cost": 4},
            {"category": "Beverages", "item": "Tea (Medium)", "price": 15, "cost": 6},
            {"category": "Beverages", "item": "Tea (Large)", "price": 20, "cost": 8},
            {"category": "Beverages", "item": "Coffee", "price": 20, "cost": 10},
            {"category": "Snacks", "item": "Maggi", "price": 40, "cost": 15},
            {"category": "Snacks", "item": "Sandwich", "price": 50, "cost": 20}
        ])
        default_menu.to_csv(DATABASES["menu"], index=False)

    if not os.path.exists(DATABASES["inventory"]):
        pd.DataFrame(columns=["item", "stock", "threshold"]).to_csv(DATABASES["inventory"], index=False)

    if not os.path.exists(DATABASES["credit"]):
        pd.DataFrame(columns=["mobile", "amount", "type", "timestamp", "staff"]).to_csv(DATABASES["credit"], index=False)


def load_db(name):
    try:
        return pd.read_csv(DATABASES[name])
    except:
        return pd.DataFrame()


def save_db(name, df):
    df.to_csv(DATABASES[name], index=False)

# ======================
# APP INIT
# ======================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)

init_data()

if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ======================
# LOGIN SIDEBAR
# ======================
with st.sidebar:
    st.title("Login")
    if not st.session_state.authenticated:
        role = st.selectbox("Select Role", ["Admin", "Staff"])
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if PASSWORDS.get(role) == password:
                st.session_state.user_role = role
                st.session_state.authenticated = True
                st.success(f"Logged in as {role}")
                st.rerun()
            else:
                st.error("Incorrect password")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.rerun()

# ======================
# TABS & FEATURES
# ======================
if st.session_state.authenticated:
    tabs = ["Order", "Customers"]
    if st.session_state.user_role == "Admin":
        tabs += ["Inventory", "Reports", "Backup"]

    selected_tab = st.tabs(tabs)

    # Order Tab
    with selected_tab[0]:
        st.header("Order Placement")
        st.info("Order placement interface will go here.")

    # Customers Tab
    with selected_tab[1]:
        st.header("Customer Management")
        st.info("Customer search, credit management and history coming soon.")

    # Admin Tabs
    if st.session_state.user_role == "Admin":
        # Inventory
        with selected_tab[2]:
            st.header("Inventory Management")
            inventory_df = load_db("inventory")
            st.dataframe(inventory_df)
            st.info("Inventory management features will go here.")

        # Reports
        with selected_tab[3]:
            st.header("Sales Reports")
            st.info("Sales analytics and performance charts will go here.")

        # Backup
        with selected_tab[4]:
            st.header("Data Backup")
            if st.button("Create Backup Now"):
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                backup_dir = os.path.join(BACKUP_FOLDER, timestamp)
                os.makedirs(backup_dir, exist_ok=True)
                for name, path in DATABASES.items():
                    if os.path.exists(path):
                        shutil.copy2(path, os.path.join(backup_dir, os.path.basename(path)))
                st.success(f"Backup created in folder: {backup_dir}")
else:
    st.warning("Please log in using the sidebar to use the app.")
    
