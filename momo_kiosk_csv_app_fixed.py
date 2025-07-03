
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import os

DATA_DIR = "data/"
os.makedirs(DATA_DIR, exist_ok=True)

USERS_CSV = os.path.join(DATA_DIR, "users.csv")
ORDERS_CSV = os.path.join(DATA_DIR, "orders.csv")
CUSTOMERS_CSV = os.path.join(DATA_DIR, "customers.csv")
MENU_CSV = os.path.join(DATA_DIR, "menu.csv")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_csv(file, default_df):
    if os.path.exists(file):
        return pd.read_csv(file)
    else:
        default_df.to_csv(file, index=False)
        return default_df

def save_csv(df, file):
    df.to_csv(file, index=False)

def authenticate(username, password):
    users_df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    user = users_df[users_df['username'] == username]
    if not user.empty and user.iloc[0]['password'] == hash_password(password):
        return user.iloc[0]['role'], user.iloc[0]['access_pages'].split(',')
    return None, None

if not os.path.exists(USERS_CSV):
    save_csv(pd.DataFrame([{
        'username': 'admin',
        'password': hash_password('admin123'),
        'role': 'Admin',
        'access_pages': 'all'
    }]), USERS_CSV)

if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_pages' not in st.session_state:
    st.session_state.user_pages = []

if not st.session_state.current_user:
    st.title("Momo Kiosk Pro - Login")
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

def orders_page():
    st.subheader("Orders Page")
    st.info("Order placement UI goes here.")

def customers_page():
    st.subheader("Customer Management")
    st.info("Customer data UI goes here.")

def inventory_page():
    st.subheader("Inventory Management")
    st.info("Menu and stock management goes here.")

def reports_page():
    st.subheader("Reports Dashboard")
    if os.path.exists(ORDERS_CSV):
        orders_df = pd.read_csv(ORDERS_CSV)
        orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
        orders_df['date'] = orders_df['timestamp'].dt.date
        orders_df['week'] = orders_df['timestamp'].dt.strftime('%Y-%U')
        orders_df['month'] = orders_df['timestamp'].dt.strftime('%Y-%m')
        tab1, tab2, tab3 = st.tabs(["Daily", "Weekly", "Monthly"])
        with tab1:
            st.write(orders_df.groupby('date')['total'].sum().reset_index().rename(columns={'total': 'Daily Sales'}))
        with tab2:
            st.write(orders_df.groupby('week')['total'].sum().reset_index().rename(columns={'total': 'Weekly Sales'}))
        with tab3:
            st.write(orders_df.groupby('month')['total'].sum().reset_index().rename(columns={'total': 'Monthly Sales'}))
    else:
        st.warning("No orders data available.")

def manage_users_page():
    st.subheader("Manage Users (Admin Only)")
    users_df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    st.dataframe(users_df[['username', 'role', 'access_pages']])
    with st.form("add_user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["Staff", "Admin"])
        access_options = st.multiselect("Page Access", ["Orders", "Customers", "Inventory", "Reports"])
        if st.form_submit_button("Create User"):
            if new_username in users_df['username'].values:
                st.error("Username already exists!")
            else:
                access_str = ','.join(access_options) if new_role != 'Admin' else 'all'
                new_user = pd.DataFrame([{
                    'username': new_username,
                    'password': hash_password(new_password),
                    'role': new_role,
                    'access_pages': access_str
                }])
                users_df = pd.concat([users_df, new_user], ignore_index=True)
                save_csv(users_df, USERS_CSV)
                st.success("User added successfully!")
                st.rerun()

st.title("Momo Kiosk Pro")
st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")

pages = {
    "Orders": orders_page,
    "Customers": customers_page,
    "Inventory": inventory_page,
    "Reports": reports_page
}
if st.session_state.user_role == 'Admin':
    pages["Manage"] = manage_users_page

visible_tabs = st.session_state.user_pages
selected = st.sidebar.radio("Navigate", visible_tabs)
pages[selected]()

if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.user_pages = []
    st.rerun()
