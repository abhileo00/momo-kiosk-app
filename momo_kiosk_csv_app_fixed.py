# food_hub_app.py

import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import os
import ast
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional

# Constants
DATA_DIR = "data/"
os.makedirs(DATA_DIR, exist_ok=True)
USERS_CSV = os.path.join(DATA_DIR, "users.csv")
ORDERS_CSV = os.path.join(DATA_DIR, "orders.csv")
CUSTOMERS_CSV = os.path.join(DATA_DIR, "customers.csv")
MENU_CSV = os.path.join(DATA_DIR, "menu.csv")
BACKUP_DIR = os.path.join(DATA_DIR, "backups/")
os.makedirs(BACKUP_DIR, exist_ok=True)

# Utils
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_backup(file_path: str):
    try:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}.bak")
            pd.read_csv(file_path).to_csv(backup_path, index=False)
    except Exception as e:
        st.error(f"Backup failed: {str(e)}")

def load_csv(file: str, default_df: pd.DataFrame) -> pd.DataFrame:
    try:
        if os.path.exists(file):
            return pd.read_csv(file)
        else:
            default_df.to_csv(file, index=False)
            return default_df
    except Exception as e:
        st.error(f"Error loading {file}: {str(e)}")
        return default_df.copy()

def save_csv(df: pd.DataFrame, file: str):
    try:
        create_backup(file)
        df.to_csv(file, index=False)
    except Exception as e:
        st.error(f"Error saving {file}: {str(e)}")

def authenticate(username: str, password: str) -> Tuple[Optional[str], Optional[List[str]]]:
    users_df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    user = users_df[users_df['username'] == username]
    if not user.empty and user.iloc[0]['password'] == hash_password(password):
        return user.iloc[0]['role'], user.iloc[0]['access_pages'].split(',')
    return None, None

def initialize_default_admin():
    if not os.path.exists(USERS_CSV):
        save_csv(pd.DataFrame([{
            'username': 'admin',
            'password': hash_password('admin123'),
            'role': 'Admin',
            'access_pages': 'all'
        }]), USERS_CSV)

def initialize_session_state():
    defaults = {
        'current_user': None,
        'user_role': None,
        'user_pages': [],
        'current_order': [],
        'edit_item': None,
        'login_form_password': ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def login_page():
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

def orders_page():
    st.header("Orders Management")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    if menu_df.empty:
        st.warning("No items in menu.")
        return

    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Category", menu_df['category'].unique())
    with col2:
        search_term = st.text_input("Search Items")
    selected_items = menu_df[menu_df['category'] == category]
    if search_term:
        selected_items = selected_items[selected_items['item'].str.contains(search_term, case=False)]

    added_items = []
    for _, item in selected_items.iterrows():
        qty = st.number_input(
            f"{item['item']} (₹{item['price']}) - Stock: {int(item['stock'])}",
            min_value=0,
            max_value=int(item['stock']),
            key=f"qty_{item['item']}"
        )
        if qty > 0:
            added_items.append({
                'item': item['item'],
                'price': item['price'],
                'quantity': qty,
                'total': qty * item['price']
            })

    if added_items:
        st.session_state.current_order = added_items
        order_df = pd.DataFrame(added_items)
        st.subheader("Current Order")
        st.dataframe(order_df)
        total = order_df['total'].sum()
        st.markdown(f"**Total: ₹{total:.2f}**")

        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online Payment"])
        customer = st.text_input("Customer Phone/Name", help="Required for credit orders")

        if payment == "Credit" and not customer.strip():
            st.warning("Phone number is required for credit orders.")
            return

        if st.button("Submit Order"):
            process_order(customer, payment, total, added_items)
            st.success("Order placed successfully!")
            st.session_state.current_order = []
            st.rerun()

def process_order(customer: str, payment: str, total: float, items: List[dict]):
    orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
    new_order = pd.DataFrame([{
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'customer': customer.strip() if customer else 'Guest',
        'items': str(items),
        'total': total,
        'payment_mode': payment,
        'staff': st.session_state.current_user
    }])
    orders_df = pd.concat([orders_df, new_order], ignore_index=True)
    save_csv(orders_df, ORDERS_CSV)

    menu_df = load_csv(MENU_CSV, pd.DataFrame())
    menu_df.set_index("item", inplace=True)
    for item in items:
        if item["item"] in menu_df.index:
            menu_df.at[item["item"], "stock"] -= item["quantity"]
    menu_df.reset_index(inplace=True)
    save_csv(menu_df, MENU_CSV)

def reports_page():
    st.header("Sales Reports")
    if not os.path.exists(ORDERS_CSV):
        st.info("No orders yet.")
        return

    df = pd.read_csv(ORDERS_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.strftime('%Y-%U')
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')
    df['items'] = df['items'].apply(ast.literal_eval)

    tab1, tab2, tab3, tab4 = st.tabs(["Daily Summary", "Weekly", "Monthly", "Item Analysis"])

    with tab1:
        daily = df.groupby('date').agg({'total': 'sum'}).reset_index()
        st.dataframe(daily)
        fig, ax = plt.subplots()
        ax.plot(daily['date'], daily['total'], marker='o')
        ax.set_title("Daily Sales")
        st.pyplot(fig)

    with tab2:
        weekly = df.groupby('week').agg({'total': 'sum'}).reset_index()
        st.dataframe(weekly)

    with tab3:
        monthly = df.groupby('month').agg({'total': 'sum'}).reset_index()
        st.dataframe(monthly)

    with tab4:
        items_df = df.explode('items')
        items_data = pd.concat([items_df.drop('items', axis=1), items_df['items'].apply(pd.Series)], axis=1)
        item_sales = items_data.groupby('item').agg({'quantity': 'sum', 'total': 'sum'}).reset_index()
        st.dataframe(item_sales.sort_values('total', ascending=False))

def inventory_page():
    st.header("Inventory Management")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    st.dataframe(menu_df)

    with st.expander("Add/Edit Item"):
        with st.form("item_form"):
            category = st.selectbox("Category", ["Appetizer", "Main Course", "Dessert", "Beverage"])
            item = st.text_input("Item Name")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Stock", min_value=0)

            if st.form_submit_button("Save Item"):
                if not item.strip():
                    st.error("Item name required")
                else:
                    new_item = pd.DataFrame([{
                        "category": category,
                        "item": item,
                        "price": price,
                        "cost": cost,
                        "stock": stock
                    }])
                    menu_df = pd.concat([menu_df, new_item], ignore_index=True)
                    save_csv(menu_df, MENU_CSV)
                    st.success("Item saved")
                    st.rerun()

def customers_page():
    st.header("Customers")
    df = load_csv(CUSTOMERS_CSV, pd.DataFrame(columns=["name", "phone", "email", "join_date", "total_orders", "total_spent"]))
    st.dataframe(df)

def manage_users_page():
    st.header("User Management")
    df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    st.dataframe(df[['username', 'role', 'access_pages']])

    with st.expander("Add User"):
        with st.form("new_user_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Admin", "Staff"])
            pages = st.multiselect("Pages", ["Orders", "Customers", "Inventory", "Reports"])
            if st.form_submit_button("Create User"):
                if username in df['username'].values:
                    st.warning("User already exists")
                else:
                    new_user = pd.DataFrame([{
                        'username': username,
                        'password': hash_password(password),
                        'role': role,
                        'access_pages': 'all' if role == "Admin" else ','.join(pages)
                    }])
                    df = pd.concat([df, new_user], ignore_index=True)
                    save_csv(df, USERS_CSV)
                    st.success("User created")
                    st.rerun()

def main_app():
    st.title("Food Hub - Restaurant Management System")
    st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")

    pages = {
        "Orders": orders_page,
        "Customers": customers_page,
        "Inventory": inventory_page,
        "Reports": reports_page,
        "Manage": manage_users_page
    }

    if st.session_state.user_role == "Admin":
        visible_tabs = list(pages.keys())
    else:
        visible_tabs = st.session_state.user_pages

    selected_tab = st.selectbox("Select Page", visible_tabs)
    if selected_tab in pages:
        pages[selected_tab]()

# App Runner
if __name__ == "__main__" or st._is_running_with_streamlit:
    initialize_default_admin()
    initialize_session_state()
    if not st.session_state.current_user:
        login_page()
    else:
        main_app()
