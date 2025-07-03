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
    """Hash password using SHA-256 algorithm."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_backup(file_path: str):
    """Create backup of important data files"""
    try:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}.bak")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df.to_csv(backup_path, index=False)
    except Exception as e:
        st.error(f"Backup failed: {str(e)}")

def load_csv(file: str, default_df: pd.DataFrame) -> pd.DataFrame:
    """Load CSV file or create with default DataFrame if doesn't exist."""
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
    """Save DataFrame to CSV with backup."""
    try:
        create_backup(file)
        df.to_csv(file, index=False)
    except Exception as e:
        st.error(f"Error saving {file}: {str(e)}")

def authenticate(username: str, password: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """Authenticate user and return role and accessible pages."""
    users_df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    user = users_df[users_df['username'] == username]
    
    if not user.empty and user.iloc[0]['password'] == hash_password(password):
        return user.iloc[0]['role'], user.iloc[0]['access_pages'].split(',')
    return None, None

def initialize_default_admin():
    """Create default admin user if none exists."""
    if not os.path.exists(USERS_CSV):
        save_csv(pd.DataFrame([{
            'username': 'admin',
            'password': hash_password('admin123'),
            'role': 'Admin',
            'access_pages': 'all'
        }]), USERS_CSV)

def initialize_session_state():
    """Initialize all required session state variables."""
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'user_pages' not in st.session_state:
        st.session_state.user_pages = []
    if 'current_order' not in st.session_state:
        st.session_state.current_order = []

def login_page():
    """Render the login page."""
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
                # Clear password field on failed attempt
                st.session_state.login_form_password = ""
    st.stop()

def orders_page():
    """Render the orders page."""
    st.header("Orders Management")
    menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
    
    if menu_df.empty:
        st.warning("No items in menu. Please add items to the inventory first.")
        return

    # Menu selection
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Category", menu_df['category'].unique())
    with col2:
        search_term = st.text_input("Search Items")
    
    selected_items = menu_df[menu_df['category'] == category]
    if search_term:
        selected_items = selected_items[selected_items['item'].str.contains(search_term, case=False)]

    # Item selection
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

    # Order summary
    if added_items:
        st.session_state.current_order = added_items
        order_df = pd.DataFrame(added_items)
        st.subheader("Current Order")
        st.dataframe(order_df)
        
        total = order_df['total'].sum()
        st.markdown(f"**Total: ₹{total:.2f}**")
        
        # Payment and customer info
        payment = st.radio("Payment Mode", ["Cash", "Credit", "Online Payment"])
        customer = st.text_input("Customer Phone/Name", help="Required for credit orders")
        
        # Validation
        if payment == "Credit" and not customer.strip():
            st.warning("Phone number is required for credit orders.")
            return
        
        if st.button("Submit Order", type="primary"):
            with st.spinner("Processing order..."):
                process_order(customer, payment, total, added_items)
                st.success("Order placed successfully!")
                st.session_state.current_order = []
                st.rerun()

def process_order(customer: str, payment: str, total: float, items: List[dict]):
    """Process and save the order."""
    orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
    new_order = pd.DataFrame([{
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'customer': customer.strip() if customer.strip() else 'Guest',
        'items': str(items),
        'total': total,
        'payment_mode': payment,
        'staff': st.session_state.current_user
    }])
    
    orders_df = pd.concat([orders_df, new_order], ignore_index=True)
    save_csv(orders_df, ORDERS_CSV)
    
    # Update inventory
    menu_df = load_csv(MENU_CSV, pd.DataFrame())
    menu_df.set_index("item", inplace=True)
    for item in items:
        menu_df.at[item["item"], "stock"] -= item["quantity"]
    menu_df.reset_index(inplace=True)
    save_csv(menu_df, MENU_CSV)

def reports_page():
    """Render the reports page."""
    st.header("Sales Reports")
    if not os.path.exists(ORDERS_CSV):
        st.info("No orders yet.")
        return

    df = pd.read_csv(ORDERS_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.strftime('%Y-%U')
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')
    df['items'] = df['items'].apply(ast.literal_eval)  # Safer than eval

    tab1, tab2, tab3, tab4 = st.tabs(["Daily Summary", "Weekly", "Monthly", "Item Analysis"])

    with tab1:
        st.subheader("Daily Sales Summary")
        daily_sales = df.groupby('date').agg({'total': 'sum', 'payment_mode': lambda x: x.value_counts().to_dict()}).reset_index()
        daily_sales.rename(columns={'total': 'Total Sales'}, inplace=True)
        st.dataframe(daily_sales)

    with tab2:
        st.subheader("Weekly Sales Summary")
        weekly_sales = df.groupby('week').agg({'total': 'sum'}).reset_index()
        weekly_sales.rename(columns={'total': 'Total Sales'}, inplace=True)
        st.dataframe(weekly_sales)

    with tab3:
        st.subheader("Monthly Sales Summary")
        monthly_sales = df.groupby('month').agg({'total': 'sum'}).reset_index()
        monthly_sales.rename(columns={'total': 'Total Sales'}, inplace=True)
        st.dataframe(monthly_sales)

    with tab4:
        st.subheader("Item Sales Analysis")
        items_df = df.explode('items')
        items_data = pd.concat([items_df.drop('items', axis=1), items_df['items'].apply(pd.Series)], axis=1)
        
        col1, col2 = st.columns(2)
        with col1:
            time_period = st.selectbox("View by", ["Daily", "Weekly", "Monthly"])
        with col2:
            top_n = st.number_input("Show top items", min_value=5, max_value=20, value=10)
        
        if time_period == "Daily":
            group_col = 'date'
        elif time_period == "Weekly":
            group_col = 'week'
        else:
            group_col = 'month'
        
        item_sales = items_data.groupby([group_col, 'item']).agg({
            'quantity': 'sum',
            'total': 'sum'
        }).reset_index().sort_values([group_col, 'total'], ascending=[True, False])
        
        st.dataframe(item_sales)
        
        # Top selling items
        st.subheader(f"Top {top_n} Selling Items")
        top_items = items_data.groupby('item').agg({
            'quantity': 'sum',
            'total': 'sum'
        }).nlargest(top_n, 'total')
        st.dataframe(top_items)

def manage_users_page():
    """Render the user management page."""
    st.header("User Management")
    df = load_csv(USERS_CSV, pd.DataFrame(columns=['username', 'password', 'role', 'access_pages']))
    
    # View existing users
    st.subheader("Current Users")
    st.dataframe(df[['username', 'role', 'access_pages']])
    
    # Add new user
    with st.expander("Add New User"):
        with st.form("add_user"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            r = st.selectbox("Role", ["Staff", "Admin"])
            pages = st.multiselect("Accessible Pages", ["Orders", "Customers", "Inventory", "Reports"])
            
            if st.form_submit_button("Create User"):
                if not u.strip() or not p.strip():
                    st.error("Username and password cannot be empty.")
                elif u in df['username'].values:
                    st.error("Username already exists")
                else:
                    new_user = pd.DataFrame([{
                        "username": u,
                        "password": hash_password(p),
                        "role": r,
                        "access_pages": 'all' if r == 'Admin' else ','.join(pages)
                    }])
                    df = pd.concat([df, new_user], ignore_index=True)
                    save_csv(df, USERS_CSV)
                    st.success("User created successfully!")
                    st.rerun()

def placeholder_page(label: str):
    """Placeholder for unimplemented pages."""
    st.subheader(f"{label} Management")
    st.info("This section is under development and will be available soon.")

def main_app():
    """Main application after login."""
    st.title("Food Hub - Restaurant Management System")
    st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")
    
    # Navigation
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
    
    # Logout button
    if st.sidebar.button("Logout", type="primary"):
        for key in ['current_user', 'user_role', 'user_pages', 'current_order']:
            st.session_state.pop(key, None)
        st.rerun()

# Initialize the app
initialize_default_admin()
initialize_session_state()

if not st.session_state.current_user:
    login_page()
else:
    main_app()
