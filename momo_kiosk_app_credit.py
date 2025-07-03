import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import shutil

# ======================
# DATA CONFIGURATION
# ======================
DATA_FOLDER = "momo_kiosk_data/"
DATABASES = {
    "orders": DATA_FOLDER + "orders.csv",
    "menu": DATA_FOLDER + "menu.csv",
    "customers": DATA_FOLDER + "customers.csv",
    "credit": DATA_FOLDER + "credit_transactions.csv",
    "inventory": DATA_FOLDER + "inventory.csv"
}

TOPPINGS = {
    "Extra Cheese": 20,
    "Masala": 10,
    "Butter": 10,
    "Egg": 15
}

CUSTOMER_COLUMNS = [
    "mobile", "name", "credit_balance", "total_spent",
    "order_count", "first_order", "last_order", "loyalty_points"
]

MENU_ITEMS = {
    "Veg Momo": {"price": 80, "category": "Steamed"},
    "Chicken Momo": {"price": 100, "category": "Steamed"},
    "Fried Momo": {"price": 120, "category": "Fried"},
    "Jhol Momo": {"price": 110, "category": "Soup"},
    "Chilli Momo": {"price": 130, "category": "Fried"},
    "Paneer Momo": {"price": 90, "category": "Steamed"}
}

# ======================
# DATA MANAGEMENT
# ======================
def init_data_system():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        os.makedirs(DATA_FOLDER + "backups/")

    # Initialize menu database
    if not os.path.exists(DATABASES["menu"]):
        menu_df = pd.DataFrame.from_dict(MENU_ITEMS, orient='index').reset_index()
        menu_df = menu_df.rename(columns={'index': 'item'})
        menu_df.to_csv(DATABASES["menu"], index=False)

    # Initialize customers database
    if not os.path.exists(DATABASES["customers"]):
        pd.DataFrame(columns=CUSTOMER_COLUMNS).to_csv(DATABASES["customers"], index=False)

    # Initialize other databases with empty DataFrames if they don't exist
    for db in ["orders", "credit", "inventory"]:
        if not os.path.exists(DATABASES[db]):
            pd.DataFrame().to_csv(DATABASES[db], index=False)

def load_db(db_name):
    try:
        return pd.read_csv(DATABASES[db_name])
    except:
        return pd.DataFrame()

def save_db(db_name, df):
    df.to_csv(DATABASES[db_name], index=False)

def get_customer(mobile):
    customers_df = load_db("customers")
    if not customers_df.empty and mobile in customers_df['mobile'].values:
        return customers_df[customers_df['mobile'] == mobile].iloc[0].to_dict()
    return None

def update_customer(mobile, name=None, amount=0, order_placed=False):
    customers_df = load_db("customers")
    
    if not customers_df.empty and mobile in customers_df['mobile'].values:
        # Update existing customer
        idx = customers_df[customers_df['mobile'] == mobile].index[0]
        
        if order_placed:
            customers_df.at[idx, 'order_count'] += 1
            customers_df.at[idx, 'total_spent'] += amount
            customers_df.at[idx, 'last_order'] = datetime.now().strftime('%Y-%m-%d')
            customers_df.at[idx, 'loyalty_points'] += int(amount / 10)  # 1 point per Rs.10 spent
            
        if name:
            customers_df.at[idx, 'name'] = name
            
    else:
        # Create new customer
        new_customer = {
            "mobile": mobile,
            "name": name if name else "New Customer",
            "credit_balance": 0,
            "total_spent": amount if order_placed else 0,
            "order_count": 1 if order_placed else 0,
            "first_order": datetime.now().strftime('%Y-%m-%d') if order_placed else "",
            "last_order": datetime.now().strftime('%Y-%m-%d') if order_placed else "",
            "loyalty_points": int(amount / 10) if order_placed else 0
        }
        customers_df = pd.concat([customers_df, pd.DataFrame([new_customer])], ignore_index=True)
    
    save_db("customers", customers_df)

def calculate_total(order_items):
    total = 0
    for item in order_items:
        total += item['price'] * item['quantity']
        for topping in item.get('toppings', []):
            total += TOPPINGS.get(topping, 0) * item['quantity']
    return total

def create_backup():
    backup_folder = DATA_FOLDER + "backups/" + datetime.now().strftime("%Y%m%d_%H%M%S") + "/"
    os.makedirs(backup_folder)
    for db_file in DATABASES.values():
        shutil.copy2(db_file, backup_folder)
    return backup_folder

# ======================
# STREAMLIT APP
# ======================
st.set_page_config(page_title="Momo Kiosk Pro", layout="wide")
init_data_system()

# Initialize session state
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "current_order" not in st.session_state:
    st.session_state.current_order = {
        "items": [],
        "customer_mobile": "",
        "customer_name": "",
        "payment_method": "Cash",
        "paid": False
    }

# Login Sidebar
with st.sidebar:
    st.title("🔐 Login")
    if not st.session_state.user_role:
        role = st.selectbox("Select Role", ["Staff", "Admin"])
        if st.button("Login"):
            st.session_state.user_role = role
            st.rerun()
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        if st.button("Logout"):
            st.session_state.user_role = None
            st.rerun()

# Main App
if st.session_state.user_role:
    # Tabs setup based on role
    tabs = ["📝 Order", "👥 Customers"]
    if st.session_state.user_role == "Admin":
        tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])
    
    selected_tab = st.tabs(tabs)

    # Order Tab
    with selected_tab[0]:
        st.header("📝 New Order")
        
        # Customer Information
        col1, col2 = st.columns(2)
        with col1:
            mobile = st.text_input("Mobile Number", key="order_mobile")
        with col2:
            customer_name = st.text_input("Customer Name (Optional)", key="customer_name")
        
        # Menu Selection
        st.subheader("Menu Items")
        menu_df = load_db("menu")
        
        order_items = []
        for _, item in menu_df.iterrows():
            with st.expander(f"{item['item']} - ₹{item['price']}"):
                quantity = st.number_input(f"Quantity", min_value=0, max_value=10, key=f"qty_{item['item']}")
                if quantity > 0:
                    toppings = st.multiselect(
                        f"Toppings for {item['item']}",
                        options=list(TOPPINGS.keys()),
                        key=f"top_{item['item']}"
                    )
                    order_items.append({
                        'item': item['item'],
                        'price': item['price'],
                        'quantity': quantity,
                        'toppings': toppings
                    })
        
        # Payment Section
        payment_method = st.radio("Payment Method:", 
                                 ["Cash", "Credit"], 
                                 horizontal=True)
        
        total_amount = calculate_total(order_items)
        st.subheader(f"Total Amount: ₹{total_amount}")
        
        if payment_method == "Credit":
            if not mobile:
                st.warning("Mobile number required for credit payments")
            else:
                customer = get_customer(mobile)
                if customer:
                    st.info(f"Customer: {customer.get('name', '')} | Balance: ₹{customer.get('credit_balance', 0)} | Points: {customer.get('loyalty_points', 0)}")
                    if customer['credit_balance'] < total_amount:
                        st.error("Insufficient credit balance")
                else:
                    st.info("New customer will be registered")
        
        if st.button("Place Order") and order_items:
            if payment_method == "Credit" and not mobile:
                st.error("Mobile number required for credit payments")
            else:
                # Process order
                update_customer(
                    mobile=mobile,
                    name=customer_name,
                    amount=total_amount,
                    order_placed=True
                )
                
                # Record transaction
                new_order = {
                    "order_id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "mobile": mobile if mobile else "",
                    "items": str(order_items),
                    "total": total_amount,
                    "payment_method": payment_method,
                    "paid": payment_method == "Cash",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "staff": st.session_state.user_role
                }
                
                # Save order
                orders_df = load_db("orders")
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                save_db("orders", orders_df)
                
                # Update credit balance if credit payment
                if payment_method == "Credit":
                    customers_df = load_db("customers")
                    idx = customers_df[customers_df['mobile'] == mobile].index[0]
                    customers_df.at[idx, 'credit_balance'] -= total_amount
                    save_db("customers", customers_df)
                
                st.success("Order placed successfully!")
                st.session_state.current_order = {
                    "items": [],
                    "customer_mobile": "",
                    "customer_name": "",
                    "payment_method": "Cash",
                    "paid": False
                }
                st.rerun()

    # Customers Tab
    with selected_tab[1]:
        st.header("👥 Customer Management")
        
        # Customer lookup
        search_mobile = st.text_input("Search by Mobile Number")
        if search_mobile:
            customer = get_customer(search_mobile)
            if customer:
                st.subheader(f"Customer: {customer.get('name', '')}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"Mobile: {customer['mobile']}")
                    st.write(f"Total Orders: {customer['order_count']}")
                    st.write(f"First Order: {customer['first_order']}")
                with col2:
                    st.write(f"Total Spent: ₹{customer['total_spent']}")
                    st.write(f"Loyalty Points: {customer['loyalty_points']}")
                    st.write(f"Last Order: {customer['last_order']}")
                
                # Credit management
                st.subheader("Credit Management")
                current_balance = customer['credit_balance']
                st.write(f"Current Balance: ₹{current_balance}")
                
                col1, col2 = st.columns(2)
                with col1:
                    with st.form("payment_form"):
                        payment_amount = st.number_input("Payment Amount", min_value=0, max_value=current_balance, value=0)
                        if st.form_submit_button("Record Payment") and payment_amount > 0:
                            # Update customer balance
                            customers_df = load_db("customers")
                            idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                            customers_df.at[idx, 'credit_balance'] -= payment_amount
                            save_db("customers", customers_df)
                            
                            # Record transaction
                            credit_df = load_db("credit")
                            credit_df = pd.concat([credit_df, pd.DataFrame([{
                                "mobile": search_mobile,
                                "amount": payment_amount,
                                "type": "payment",
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "staff": st.session_state.user_role
                            }])], ignore_index=True)
                            save_db("credit", credit_df)
                            st.success("Payment recorded!")
                            st.rerun()
                
                with col2:
                    with st.form("credit_form"):
                        credit_amount = st.number_input("Credit Amount", min_value=0, value=0)
                        if st.form_submit_button("Add Credit") and credit_amount > 0:
                            # Update customer balance
                            customers_df = load_db("customers")
                            idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                            customers_df.at[idx, 'credit_balance'] += credit_amount
                            save_db("customers", customers_df)
                            
                            # Record transaction
                            credit_df = load_db("credit")
                            credit_df = pd.concat([credit_df, pd.DataFrame([{
                                "mobile": search_mobile,
                                "amount": credit_amount,
                                "type": "credit",
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "staff": st.session_state.user_role
                            }])], ignore_index=True)
                            save_db("credit", credit_df)
                            st.success("Credit added!")
                            st.rerun()
            else:
                st.warning("Customer not found")

    # Admin-only tabs
    if st.session_state.user_role == "Admin":
        with selected_tab[2]:  # Inventory
            st.header("📦 Inventory Management")
            st.write("Inventory management coming soon!")
        
        with selected_tab[3]:  # Reports
            st.header("📊 Sales Reports")
            
            # Date range selector
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=date.today())
            with col2:
                end_date = st.date_input("End Date", value=date.today())
            
            if st.button("Generate Report"):
                orders_df = load_db("orders")
                if not orders_df.empty:
                    orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
                    mask = (orders_df['timestamp'].dt.date >= start_date) & (orders_df['timestamp'].dt.date <= end_date)
                    filtered_orders = orders_df.loc[mask]
                    
                    if not filtered_orders.empty:
                        st.subheader(f"Sales Report: {start_date} to {end_date}")
                        
                        # Summary stats
                        total_sales = filtered_orders['total'].sum()
                        total_orders = len(filtered_orders)
                        avg_order = total_sales / total_orders
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Total Sales", f"₹{total_sales:,.2f}")
                        col2.metric("Total Orders", total_orders)
                        col3.metric("Average Order", f"₹{avg_order:,.2f}")
                        
                        # Payment method breakdown
                        st.subheader("Payment Methods")
                        payment_counts = filtered_orders['payment_method'].value_counts()
                        st.bar_chart(payment_counts)
                        
                        # Daily sales trend
                        st.subheader("Daily Sales Trend")
                        daily_sales = filtered_orders.groupby(filtered_orders['timestamp'].dt.date)['total'].sum()
                        st.line_chart(daily_sales)
                    else:
                        st.warning("No orders found in selected date range")
                else:
                    st.warning("No order data available")
        
        with selected_tab[4]:  # Backup
            st.header("💾 System Backup")
            
            if st.button("Create Backup Now"):
                backup_path = create_backup()
                st.success(f"Backup created successfully at: {backup_path}")
            
            st.subheader("Restore Backup")
            backup_list = []
            if os.path.exists(DATA_FOLDER + "backups/"):
                backup_list = sorted(os.listdir(DATA_FOLDER + "backups/"), reverse=True)
            
            if backup_list:
                selected_backup = st.selectbox("Select backup to restore", backup_list)
                
                if st.button("Restore Selected Backup"):
                    # Copy files from backup to main data folder
                    for db_name in DATABASES.keys():
                        src = f"{DATA_FOLDER}backups/{selected_backup}/{db_name}.csv"
                        dst = DATABASES[db_name]
                        if os.path.exists(src):
                            shutil.copy2(src, dst)
                    st.success("Backup restored successfully!")
                    st.rerun()
            else:
                st.warning("No backups available")

else:
    st.title("Momo Kiosk Pro")
    st.write("Please login from the sidebar to continue")
