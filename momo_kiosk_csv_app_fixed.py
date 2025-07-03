
import streamlit as st
import pandas as pd
from datetime import datetime
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
if 'current_order' not in st.session_state:
    st.session_state.current_order = []

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
    st.header("Orders")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    if menu_df.empty:
        st.warning("No items in menu.")
        return

    category = st.selectbox("Category", menu_df['category'].unique())
    selected_items = menu_df[menu_df['category'] == category]

    added_items = []
    for _, item in selected_items.iterrows():
        qty = st.number_input(f"{item['item']} (â‚¹{item['price']}):", min_value=0, max_value=int(item['stock']), key=item['item'])
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
        st.write("Current Order:")
        st.dataframe(order_df)
        total = order_df['total'].sum()
        st.markdown(f"**Total: â‚¹{total:.2f}**")
        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online"])
        customer = ""

        if payment == "Credit":
            customer = st.text_input("Customer Phone Number (required)")
            if not customer.strip():
                st.warning("Phone number is required for credit orders.")
                return
        else:
            customer = st.text_input("Optional: Customer Name / Phone")

        if st.button("Submit Order"):
            orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
            new_order = pd.DataFrame([{
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'customer': customer.strip() if customer.strip() else 'Guest',
                'items': str(added_items),
                'total': total,
                'payment_mode': payment,
                'staff': st.session_state.current_user
            }])
            orders_df = pd.concat([orders_df, new_order], ignore_index=True)
            save_csv(orders_df, ORDERS_CSV)

            menu_df.set_index("item", inplace=True)
            for i in added_items:
                menu_df.at[i["item"], "stock"] -= i["quantity"]
            menu_df.reset_index(inplace=True)
            save_csv(menu_df, MENU_CSV)
            st.session_state.current_order = []
            st.success("Order placed successfully!")
            st.rerun()

def reports_page():
    st.header("Reports")
    if not os.path.exists(ORDERS_CSV):
        st.info("No orders yet.")
        return

    df = pd.read_csv(ORDERS_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.strftime('%Y-%U')
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')

    tab1, tab2, tab3, tab4 = st.tabs(["Daily Summary", "Weekly", "Monthly", "Daily Item Sales"])

    with tab1:
        st.subheader("Daily Summary")
        st.dataframe(df.groupby('date')['total'].sum().reset_index().rename(columns={'total': 'Sales'}))

    with tab2:
        st.subheader("Weekly Summary")
        st.dataframe(df.groupby('week')['total'].sum().reset_index().rename(columns={'total': 'Sales'}))

    with tab3:
        st.subheader("Monthly Summary")
        st.dataframe(df.groupby('month')['total'].sum().reset_index().rename(columns={'total': 'Sales'}))

    with tab4:
        st.subheader("Daily Item-wise Sales")
        df['items'] = df['items'].apply(eval)
        items = df.explode('items')
        items_df = pd.concat([items.drop('items', axis=1), items['items'].apply(pd.Series)], axis=1)
        grouped = items_df.groupby(['date', 'item']).agg({'quantity': 'sum', 'total': 'sum'}).reset_index()
        st.dataframe(grouped.sort_values(['date', 'item']))

# Other pages unchanged for brevity
def placeholder_page(label): st.subheader(label + " Page (Coming Soon)")

def manage_users_page():
    st.header("Manage Users")
    df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    st.dataframe(df[['username', 'role', 'access_pages']])
    with st.form("add_user"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        r = st.selectbox("Role", ["Staff", "Admin"])
        pages = st.multiselect("Pages", ["Orders", "Customers", "Inventory", "Reports"])
        if st.form_submit_button("Create"):
            if not u.strip() or not p.strip():
                st.error("Username and password cannot be empty.")
                return
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

# Main layout with top-tab navigation
st.title("Momo Kiosk Pro")
st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")

pages = {
    "Orders": orders_page,
    "Customers": lambda: placeholder_page("Customers"),
    "Inventory": lambda: placeholder_page("Inventory"),
    "Reports": reports_page,
    "Manage": manage_users_page
}
visible_tabs = st.session_state.user_pages
if st.session_state.user_role == "Admin":
    visible_tabs = list(pages.keys())
tab_objs = st.tabs(visible_tabs)
for i, label in enumerate(visible_tabs):
    with tab_objs[i]:
        pages[label]()

if st.sidebar.button("Logout"):
    for key in ['current_user', 'user_role', 'user_pages', 'current_order']:
        st.session_state.pop(key, None)
    st.rerun()
