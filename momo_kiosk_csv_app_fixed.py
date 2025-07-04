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

# Initialize default admin if not exists
if not os.path.exists(USERS_CSV):
    save_csv(pd.DataFrame([{
        'username': 'admin',
        'password': hash_password('admin123'),
        'role': 'Admin',
        'access_pages': 'all'
    }]), USERS_CSV)

# Initialize session state
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

# All Application Pages
def orders_page():
    st.header("Orders Management")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    
    if menu_df.empty:
        st.warning("No items in menu. Please add items to inventory first.")
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
            f"{item['item']} (${item['price']}) - Stock: {int(item['stock'])}",
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
        st.markdown(f"**Total: ${total:.2f}**")
        
        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online"])
        customer = st.text_input("Customer Info", help="Required for credit orders")
        
        if payment == "Credit" and not customer.strip():
            st.warning("Customer info required for credit orders")
            return
        
        if st.button("Submit Order", type="primary"):
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
            
            # Update inventory
            menu_df.set_index("item", inplace=True)
            for item in added_items:
                menu_df.at[item["item"], "stock"] -= item["quantity"]
            menu_df.reset_index(inplace=True)
            save_csv(menu_df, MENU_CSV)
            
            st.success("Order placed successfully!")
            st.session_state.current_order = []
            st.rerun()

def customers_page():
    st.header("Customers Management")
    customers_df = load_csv(CUSTOMERS_CSV, pd.DataFrame(columns=["name", "phone", "email", "join_date"]))
    orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
    
    st.subheader("Customer Database")
    st.dataframe(customers_df)
    
    with st.expander("Add New Customer"):
        with st.form("add_customer"):
            name = st.text_input("Full Name")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email")
            
            if st.form_submit_button("Save Customer"):
                if not name.strip() or not phone.strip():
                    st.error("Name and phone are required")
                else:
                    new_customer = pd.DataFrame([{
                        "name": name,
                        "phone": phone,
                        "email": email,
                        "join_date": datetime.now().strftime('%Y-%m-%d')
                    }])
                    
                    customers_df = pd.concat([customers_df, new_customer], ignore_index=True)
                    save_csv(customers_df, CUSTOMERS_CSV)
                    st.success("Customer added successfully!")
                    st.rerun()

def inventory_page():
    st.header("Inventory Management")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    
    st.subheader("Current Menu")
    st.dataframe(menu_df)
    
    with st.expander("Add/Edit Menu Item"):
        with st.form("menu_item_form"):
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Category", ["Appetizer", "Main Course", "Dessert", "Beverage"])
                item_name = st.text_input("Item Name")
            with col2:
                price = st.number_input("Price ($)", min_value=0.0, step=0.5)
                stock = st.number_input("Stock", min_value=0, step=1)
            
            cost = st.number_input("Cost ($)", min_value=0.0, step=0.5)
            
            if st.form_submit_button("Save Item"):
                if not item_name.strip():
                    st.error("Item name is required")
                else:
                    new_item = pd.DataFrame([{
                        "category": category,
                        "item": item_name,
                        "price": price,
                        "cost": cost,
                        "stock": stock
                    }])
                    
                    menu_df = pd.concat([menu_df, new_item], ignore_index=True)
                    save_csv(menu_df, MENU_CSV)
                    st.success("Item saved successfully!")
                    st.rerun()

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

    tab1, tab2, tab3 = st.tabs(["Daily", "Weekly", "Monthly"])
    
    with tab1:
        st.subheader("Daily Sales")
        daily = df.groupby('date').agg({'total': 'sum'}).reset_index()
        st.dataframe(daily)
        
    with tab2:
        st.subheader("Weekly Sales")
        weekly = df.groupby('week').agg({'total': 'sum'}).reset_index()
        st.dataframe(weekly)
    
    with tab3:
        st.subheader("Monthly Sales")
        monthly = df.groupby('month').agg({'total': 'sum'}).reset_index()
        st.dataframe(monthly)

def manage_users_page():
    st.header("User Management")
    users_df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    
    st.subheader("Current Users")
    st.dataframe(users_df[['username', 'role']])
    
    with st.expander("Add New User"):
        with st.form("add_user_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Staff", "Admin"])
            
            if st.form_submit_button("Create User"):
                if not username.strip() or not password.strip():
                    st.error("Username and password are required")
                elif username in users_df['username'].values:
                    st.error("Username already exists")
                else:
                    new_user = pd.DataFrame([{
                        "username": username,
                        "password": hash_password(password),
                        "role": role,
                        "access_pages": 'all' if role == 'Admin' else 'Orders'
                    }])
                    
                    users_df = pd.concat([users_df, new_user], ignore_index=True)
                    save_csv(users_df, USERS_CSV)
                    st.success("User created successfully!")
                    st.rerun()

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

# Determine which pages to show based on user permissions
if st.session_state.user_role == "Admin":
    visible_pages = list(PAGES.keys())
else:
    visible_pages = st.session_state.user_pages

# Create tabs for navigation
tabs = st.tabs(visible_pages)

# Display the selected page
for tab, page_name in zip(tabs, visible_pages):
    with tab:
        PAGES[page_name]()

# Logout button
if st.sidebar.button("Logout", type="primary"):
    for key in ['current_user', 'user_role', 'user_pages', 'current_order']:
        st.session_state.pop(key, None)
    st.rerun()
