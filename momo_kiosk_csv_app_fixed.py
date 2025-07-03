import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import os
import ast
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional, Dict
import base64

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
    required_keys = {
        'current_user': None,
        'user_role': None,
        'user_pages': [],
        'current_order': [],
        'edit_item': None,
        'login_form_password': ""
    }
    
    for key, default_value in required_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def login_page():
    """Render the login page."""
    st.title("Food Hub - Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password", key="password_input")
        
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
    try:
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

        # Order summary
        if added_items:
            st.session_state.current_order = added_items
            order_df = pd.DataFrame(added_items)
            st.subheader("Current Order")
            st.dataframe(order_df)
            
            total = order_df['total'].sum()
            st.markdown(f"**Total: ${total:.2f}**")
            
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
    except Exception as e:
        st.error(f"An error occurred in orders page: {str(e)}")

def process_order(customer: str, payment: str, total: float, items: List[dict]):
    """Process and save the order."""
    try:
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
            if item["item"] in menu_df.index:
                menu_df.at[item["item"], "stock"] -= item["quantity"]
        menu_df.reset_index(inplace=True)
        save_csv(menu_df, MENU_CSV)
    except Exception as e:
        st.error(f"Failed to process order: {str(e)}")

def reports_page():
    """Render the reports page."""
    st.header("Sales Reports")
    try:
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
            st.subheader("Daily Sales Summary")
            daily_sales = df.groupby('date').agg({'total': 'sum', 'payment_mode': lambda x: x.value_counts().to_dict()}).reset_index()
            daily_sales.rename(columns={'total': 'Total Sales'}, inplace=True)
            st.dataframe(daily_sales)

            # Daily sales chart
            fig, ax = plt.subplots()
            ax.bar(daily_sales['date'].astype(str), daily_sales['Total Sales'])
            ax.set_title('Daily Sales Trend')
            ax.set_xlabel('Date')
            ax.set_ylabel('Total Sales ($)')
            plt.xticks(rotation=45)
            st.pyplot(fig)

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
    except Exception as e:
        st.error(f"An error occurred in reports page: {str(e)}")

def inventory_page():
    """Render the inventory management page."""
    st.header("Inventory Management")
    try:
        menu_df = load_csv(MENU_CSV, pd.DataFrame(columns=["category", "item", "price", "cost", "stock"]))
        
        # View and edit existing items
        st.subheader("Current Menu Items")
        st.dataframe(menu_df)
        
        # Add/edit items
        with st.expander("Add/Edit Menu Item"):
            if st.session_state.edit_item:
                item_to_edit = menu_df[menu_df['item'] == st.session_state.edit_item].iloc[0]
            else:
                item_to_edit = None
                
            with st.form("item_form"):
                col1, col2 = st.columns(2)
                with col1:
                    category = st.selectbox(
                        "Category",
                        ["Appetizer", "Main Course", "Dessert", "Beverage"],
                        index=0 if not item_to_edit else ["Appetizer", "Main Course", "Dessert", "Beverage"].index(item_to_edit['category'])
                    )
                    item_name = st.text_input("Item Name", value="" if not item_to_edit else item_to_edit['item'])
                with col2:
                    price = st.number_input("Price ($)", min_value=0.0, step=0.5, value=0.0 if not item_to_edit else item_to_edit['price'])
                    stock = st.number_input("Stock", min_value=0, step=1, value=0 if not item_to_edit else item_to_edit['stock'])
                
                cost = st.number_input("Cost ($)", min_value=0.0, step=0.5, value=0.0 if not item_to_edit else item_to_edit['cost'])
                
                if st.form_submit_button("Save Item"):
                    if not item_name.strip():
                        st.error("Item name cannot be empty")
                        return
                    
                    # Remove the old item if editing
                    if st.session_state.edit_item:
                        menu_df = menu_df[menu_df['item'] != st.session_state.edit_item]
                    
                    # Add the new/updated item
                    new_item = pd.DataFrame([{
                        "category": category,
                        "item": item_name,
                        "price": price,
                        "cost": cost,
                        "stock": stock
                    }])
                    
                    menu_df = pd.concat([menu_df, new_item], ignore_index=True)
                    save_csv(menu_df, MENU_CSV)
                    st.session_state.edit_item = None
                    st.success("Item saved successfully!")
                    st.rerun()
                
                if st.session_state.edit_item and st.form_submit_button("Cancel Edit"):
                    st.session_state.edit_item = None
                    st.rerun()
        
        # Edit/Delete actions
        st.subheader("Item Actions")
        selected_item = st.selectbox("Select item to edit/delete", menu_df['item'])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Edit Item"):
                st.session_state.edit_item = selected_item
                st.rerun()
        with col2:
            if st.button("Delete Item"):
                menu_df = menu_df[menu_df['item'] != selected_item]
                save_csv(menu_df, MENU_CSV)
                st.success("Item deleted successfully!")
                st.rerun()
    except Exception as e:
        st.error(f"An error occurred in inventory page: {str(e)}")

def customers_page():
    """Render the customers management page."""
    st.header("Customers Management")
    try:
        customers_df = load_csv(CUSTOMERS_CSV, pd.DataFrame(columns=["name", "phone", "email", "join_date", "total_orders", "total_spent"]))
        orders_df = load_csv(ORDERS_CSV, pd.DataFrame())
        
        # Customer analytics
        st.subheader("Customer Analytics")
        if not customers_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Customers", len(customers_df))
            with col2:
                st.metric("Top Spender", f"${customers_df['total_spent'].max():.2f}")
            with col3:
                st.metric("Most Frequent", f"{customers_df['total_orders'].max()} orders")
        
        # Customer list
        st.subheader("Customer Database")
        st.dataframe(customers_df)
        
        # Customer search
        st.subheader("Customer Lookup")
        search_term = st.text_input("Search by name or phone")
        if search_term:
            filtered_customers = customers_df[
                customers_df['name'].str.contains(search_term, case=False) | 
                customers_df['phone'].str.contains(search_term)
            ]
            st.dataframe(filtered_customers)
        
        # Customer details
        if not customers_df.empty:
            selected_customer = st.selectbox("View customer details", customers_df['name'])
            customer_data = customers_df[customers_df['name'] == selected_customer].iloc[0]
            
            with st.expander(f"Details for {selected_customer}"):
                st.write(f"**Phone:** {customer_data['phone']}")
                st.write(f"**Email:** {customer_data['email']}")
                st.write(f"**Member Since:** {customer_data['join_date']}")
                st.write(f"**Total Orders:** {customer_data['total_orders']}")
                st.write(f"**Total Spent:** ${customer_data['total_spent']:.2f}")
                
                # Customer order history
                if not orders_df.empty:
                    orders_df['items'] = orders_df['items'].apply(ast.literal_eval)
                    customer_orders = orders_df[orders_df['customer'] == selected_customer]
                    if not customer_orders.empty:
                        st.subheader("Order History")
                        st.dataframe(customer_orders)
    except Exception as e:
        st.error(f"An error occurred in customers page: {str(e)}")

def manage_users_page():
    """Render the user management page."""
    st.header("User Management")
    try:
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
        
        # User actions
        if not df.empty:
            st.subheader("User Actions")
            selected_user = st.selectbox("Select user to edit/delete", df['username'])
            user_data = df[df['username'] == selected_user].iloc[0]
            
            if user_data['username'] != st.session_state.current_user:  # Prevent self-deletion
                if st.button("Delete User"):
                    df = df[df['username'] != selected_user]
                    save_csv(df, USERS_CSV)
                    st.success("User deleted successfully!")
                    st.rerun()
            else:
                st.warning("You cannot delete your own account")
    except Exception as e:
        st.error(f"An error occurred in user management: {str(e)}")

def main_app():
    """Main application after login."""
    st.title("Food Hub - Restaurant Management System")
    st.markdown(f"Welcome, **{st.session_state.current_user}** ({st.session_state.user_role})")
    
    # Navigation
    pages = {
        "Orders": orders_page,
        "Customers": customers_page,
        "Inventory": inventory_page,
        "Reports": reports_page,
        "Manage": manage_users_page
    }
    
    visible_tabs = st.session_state.user_pages
    if st.session_state.user_role == "Admin":
        visible
