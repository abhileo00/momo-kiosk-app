
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

# Initial admin setup
if not os.path.exists(USERS_CSV):
    save_csv(pd.DataFrame([{
        'username': 'admin',
        'password': hash_password('admin123'),
        'role': 'Admin',
        'access_pages': 'all'
    }]), USERS_CSV)

# Session state
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_pages' not in st.session_state:
    st.session_state.user_pages = []
if 'current_order' not in st.session_state:
    st.session_state.current_order = []

# Login page
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

# Pages
def orders_page():
    st.subheader("Orders")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    if menu_df.empty:
        st.warning("No items in menu.")
        return

    customer = st.text_input("Customer Name / Phone")
    category = st.selectbox("Category", menu_df['category'].unique())
    selected_items = menu_df[menu_df['category'] == category]

    for _, item in selected_items.iterrows():
        qty = st.number_input(f"{item['item']} (â‚¹{item['price']}):", min_value=0, max_value=int(item['stock']), key=item['item'])
        if qty > 0:
            st.session_state.current_order.append({
                'item': item['item'],
                'price': item['price'],
                'quantity': qty,
                'total': qty * item['price']
            })

    if st.session_state.current_order:
        order_df = pd.DataFrame(st.session_state.current_order)
        st.write("Current Order:")
        st.dataframe(order_df)
        total = order_df['total'].sum()
        st.markdown(f"**Total: â‚¹{total}**")
        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online"])
        if st.button("Submit Order"):
            orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
            new_order = pd.DataFrame([{
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'customer': customer,
                'items': str(st.session_state.current_order),
                'total': total,
                'payment_mode': payment,
                'staff': st.session_state.current_user
            }])
            orders_df = pd.concat([orders_df, new_order], ignore_index=True)
            save_csv(orders_df, ORDERS_CSV)
            menu_df.set_index("item", inplace=True)
            for i in st.session_state.current_order:
                menu_df.at[i["item"], "stock"] -= i["quantity"]
            menu_df.reset_index(inplace=True)
            save_csv(menu_df, MENU_CSV)
            st.session_state.current_order = []
            st.success("Order placed successfully!")
            st.rerun()

def customers_page():
    st.subheader("Customer Management")
    df = load_csv(CUSTOMERS_CSV, pd.DataFrame(columns=["name", "phone", "credit_balance"]))
    st.dataframe(df)
    with st.form("add_customer"):
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        credit = st.number_input("Credit", min_value=0.0, value=0.0)
        if st.form_submit_button("Save"):
            df = df[df["name"] != name]
            df = pd.concat([df, pd.DataFrame([{"name": name, "phone": phone, "credit_balance": credit}])], ignore_index=True)
            save_csv(df, CUSTOMERS_CSV)
            st.success("Customer saved!")
            st.rerun()

def inventory_page():
    st.subheader("Inventory Management")
    df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    st.dataframe(df)
    with st.form("add_item"):
        cat = st.selectbox("Category", ["Momos", "Maggi", "Thali", "Tea", "Sandwich", "Other"])
        item = st.text_input("Item Name")
        price = st.number_input("Price", min_value=0.0)
        cost = st.number_input("Cost", min_value=0.0)
        stock = st.number_input("Stock", min_value=0)
        if st.form_submit_button("Add/Update"):
            df = df[df["item"] != item]
            df = pd.concat([df, pd.DataFrame([{"category": cat, "item": item, "price": price, "cost": cost, "stock": stock}])], ignore_index=True)
            save_csv(df, MENU_CSV)
            st.success("Menu updated!")
            st.rerun()

def reports_page():
    st.subheader("Sales Reports")
    if not os.path.exists(ORDERS_CSV):
        st.info("No orders to show.")
        return
    df = pd.read_csv(ORDERS_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.strftime('%Y-%U')
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')
    tab1, tab2, tab3 = st.tabs(["Daily", "Weekly", "Monthly"])
    with tab1:
        st.write(df.groupby('date')['total'].sum().reset_index().rename(columns={'total': 'Daily Sales'}))
    with tab2:
        st.write(df.groupby('week')['total'].sum().reset_index().rename(columns={'total': 'Weekly Sales'}))
    with tab3:
        st.write(df.groupby('month')['total'].sum().reset_index().rename(columns={'total': 'Monthly Sales'}))

def manage_users_page():
    st.subheader("Manage Users")
    df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    st.dataframe(df[['username', 'role', 'access_pages']])
    with st.form("add_user"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        r = st.selectbox("Role", ["Staff", "Admin"])
        pages = st.multiselect("Pages", ["Orders", "Customers", "Inventory", "Reports"])
        if st.form_submit_button("Create"):
            if u in df['username'].values:
                st.error("Username exists")
            else:
                df = pd.concat([df, pd.DataFrame([{
                    "username": u,
                    "password": hash_password(p),
                    "role": r,
                    "access_pages": 'all' if r == 'Admin' else ','.join(pages)
                }])], ignore_index=True)
                save_csv(df, USERS_CSV)
                st.success("User created!")
                st.rerun()

# Main layout
st.title("Momo Kiosk Pro")
st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")

pages = {
    "Orders": orders_page,
    "Customers": customers_page,
    "Inventory": inventory_page,
    "Reports": reports_page
}
if st.session_state.user_role == "Admin":
    pages["Manage"] = manage_users_page

selected = st.sidebar.radio("Navigate", st.session_state.user_pages)
pages[selected]()

if st.sidebar.button("Logout"):
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.user_pages = []
    st.session_state.current_order = []
    st.rerun()
