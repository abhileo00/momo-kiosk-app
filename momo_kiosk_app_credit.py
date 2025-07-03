import streamlit as st import pandas as pd from datetime import datetime import os import shutil import time

======================

CONFIGURATION

======================

APP_NAME = "Food Hub" DATA_FOLDER = "food_hub_data/" BACKUP_FOLDER = os.path.join(DATA_FOLDER, "backups") PASSWORDS = {"Admin": "admin123", "Staff": "staff123"}  # basic password protection

DATABASES = { "orders": os.path.join(DATA_FOLDER, "orders.csv"), "menu": os.path.join(DATA_FOLDER, "menu.csv"), "customers": os.path.join(DATA_FOLDER, "customers.csv"), "credit": os.path.join(DATA_FOLDER, "credit_transactions.csv"), "inventory": os.path.join(DATA_FOLDER, "inventory.csv") }

TOPPINGS = {"Extra Cheese": 20, "Masala": 10, "Butter": 10, "Egg": 15} CUSTOMER_COLUMNS = ["mobile", "name", "credit_balance", "total_spent", "order_count", "first_order", "last_order", "loyalty_points"]

======================

DATA MANAGEMENT

======================

def init_data(): os.makedirs(DATA_FOLDER, exist_ok=True) os.makedirs(BACKUP_FOLDER, exist_ok=True)

if not os.path.exists(DATABASES["customers"]):
    pd.DataFrame(columns=CUSTOMER_COLUMNS).to_csv(DATABASES["customers"], index=False)

if not os.path.exists(DATABASES["orders"]):
    pd.DataFrame(columns=["order_id", "mobile", "items", "total", "payment_method", "paid", "timestamp", "staff", "status"]).to_csv(DATABASES["orders"], index=False)

if not os.path.exists(DATABASES["menu"]):
    pd.DataFrame(columns=["category", "item", "price", "cost"]).to_csv(DATABASES["menu"], index=False)

if not os.path.exists(DATABASES["inventory"]):
    pd.DataFrame(columns=["item", "stock", "threshold"]).to_csv(DATABASES["inventory"], index=False)

if not os.path.exists(DATABASES["credit"]):
    pd.DataFrame(columns=["mobile", "amount", "type", "timestamp", "staff"]).to_csv(DATABASES["credit"], index=False)

def load_db(name): try: return pd.read_csv(DATABASES[name]) except: return pd.DataFrame()

def save_db(name, df): df.to_csv(DATABASES[name], index=False)

======================

APP START

======================

st.set_page_config(page_title=APP_NAME, layout="wide") st.title(APP_NAME)

init_data()

Login mechanism

if "user_role" not in st.session_state: st.session_state.user_role = None if "authenticated" not in st.session_state: st.session_state.authenticated = False

with st.sidebar: st.title("🔐 Login") if not st.session_state.authenticated: role = st.selectbox("Select Role", ["Admin", "Staff"]) password = st.text_input("Password", type="password") if st.button("Login"): if PASSWORDS.get(role) == password: st.session_state.user_role = role st.session_state.authenticated = True st.success(f"Logged in as {role}") st.rerun() else: st.error("Invalid password") else: st.success(f"Logged in as {st.session_state.user_role}") if st.button("Logout"): st.session_state.authenticated = False st.session_state.user_role = None st.rerun()

Tabs Setup

if st.session_state.authenticated: tabs = ["📝 Order", "👥 Customers"] if st.session_state.user_role == "Admin": tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])

selected_tab = st.tabs(tabs)

# Implementation of full features like order placement, customer management, inventory alerts, reports, etc.
# will follow here in actual full code

else: st.info("Please login from the sidebar to access the app features.")

