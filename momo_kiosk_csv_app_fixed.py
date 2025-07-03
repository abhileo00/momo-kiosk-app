
import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import os
import ast
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

# Password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_backup(file_path: str):
    try:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}.bak")
            df = pd.read_csv(file_path)
            df.to_csv(backup_path, index=False)
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
    required_keys = {
        'current_user': None,
        'user_role': None,
        'user_pages': [],
        'current_order': [],
        'edit_item': None
    }
    for key, default_value in required_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

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
                st.session_state.user_pages = pages if 'all' not in pages else ['Orders', 'Inventory', 'Reports', 'Customers', 'Manage']
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

def orders_page():
    st.header("Orders")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    if menu_df.empty:
        st.warning("Add items in inventory first.")
        return
    category = st.selectbox("Category", menu_df["category"].unique())
    selected_items = menu_df[menu_df["category"] == category]
    order_items = []
    for _, row in selected_items.iterrows():
        qty = st.number_input(f"{row['item']} - â‚¹{row['price']} (Stock: {row['stock']})", min_value=0, max_value=int(row['stock']), step=1)
        if qty > 0:
            order_items.append({
                "item": row['item'],
                "price": row['price'],
                "quantity": qty,
                "total": qty * row['price']
            })
    if order_items:
        df = pd.DataFrame(order_items)
        st.write("### Order Summary", df)
        total = df["total"].sum()
        st.success(f"Total: â‚¹{total}")
        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online"])
        customer = st.text_input("Customer Phone (required for Credit)" if payment == "Credit" else "Customer (optional)")
        if payment == "Credit" and not customer:
            st.warning("Customer phone is required for credit orders.")
            return
        if st.button("Submit Order"):
            orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
            new_order = pd.DataFrame([{
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer": customer if customer else "Guest",
                "items": str(order_items),
                "total": total,
                "payment_mode": payment,
                "staff": st.session_state.current_user
            }])
            orders_df = pd.concat([orders_df, new_order], ignore_index=True)
            save_csv(orders_df, ORDERS_CSV)
            for item in order_items:
                menu_df.loc[menu_df['item'] == item['item'], 'stock'] -= item['quantity']
            save_csv(menu_df, MENU_CSV)
            st.success("Order saved.")
            st.rerun()

def reports_page():
    st.header("Reports")
    df = load_csv(ORDERS_CSV, pd.DataFrame())
    if df.empty:
        st.info("No orders available.")
        return
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.strftime('%Y-%U')
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')
    df['items'] = df['items'].apply(ast.literal_eval)
    tabs = st.tabs(["Daily", "Weekly", "Monthly"])
    for label, col in zip(["date", "week", "month"], tabs):
        with col:
            st.subheader(f"{label.title()} Summary")
            grouped = df.groupby(label).agg({'total': 'sum'}).reset_index()
            st.dataframe(grouped)
            if st.button(f"Export {label} report as CSV", key=label):
                csv = grouped.to_csv(index=False).encode()
                st.download_button(f"Download {label}.csv", csv, f"{label}_report.csv", "text/csv")

def inventory_page():
    st.header("Inventory")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    st.dataframe(menu_df)
    with st.expander("Add Item"):
        with st.form("add_item"):
            category = st.text_input("Category")
            item = st.text_input("Item")
            price = st.number_input("Price", min_value=0.0)
            cost = st.number_input("Cost", min_value=0.0)
            stock = st.number_input("Stock", min_value=0)
            if st.form_submit_button("Save"):
                new_item = pd.DataFrame([{
                    "category": category,
                    "item": item,
                    "price": price,
                    "cost": cost,
                    "stock": stock
                }])
                menu_df = pd.concat([menu_df, new_item], ignore_index=True)
                save_csv(menu_df, MENU_CSV)
                st.success("Item saved.")
                st.rerun()

def main_app():
    st.title("ðŸ½ï¸ Food Hub")
    st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")
    pages = {
        "Orders": orders_page,
        "Inventory": inventory_page,
        "Reports": reports_page
    }
    for name, page in pages.items():
        if name in st.session_state.user_pages:
            with st.expander(f"{name} Page"):
                page()

if __name__ == "__main__":
    initialize_default_admin()
    initialize_session_state()
    if not st.session_state.current_user:
        login_page()
    else:
        main_app()
