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

# ======================
# DATA MANAGEMENT
# ======================
def init_data_system():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        os.makedirs(DATA_FOLDER + "backups/")

    # Initialize customers database
    if not os.path.exists(DATABASES["customers"]):
        pd.DataFrame(columns=CUSTOMER_COLUMNS).to_csv(DATABASES["customers"], index=False)

    # Rest of your initialization code...
    # [Keep your existing menu initialization code]

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
    
    if mobile in customers_df['mobile'].values:
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
        customers_df = customers_df.append(new_customer, ignore_index=True)
    
    save_db("customers", customers_df)

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
        
        # Payment Section
        payment_method = st.radio("Payment Method:", 
                                 ["Cash", "Credit"], 
                                 horizontal=True)
        
        if payment_method == "Credit":
            if not mobile:
                st.warning("Mobile number required for credit payments")
                st.stop()
            
            customer = get_customer(mobile)
            if customer:
                st.info(f"Customer: {customer.get('name', '')} | Balance: ₹{customer.get('credit_balance', 0)} | Points: {customer.get('loyalty_points', 0)}")
            else:
                st.info("New customer will be registered")
        
        # [Your existing order items selection code would go here]
        # For example:
        # selected_items = []
        # total_amount = calculate_total(selected_items)
        
        if st.button("Place Order"):
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
                    "mobile": mobile,
                    "items": selected_items,
                    "total": total_amount,
                    "payment_method": payment_method,
                    "paid": payment_method == "Cash",  # Credit payments are not immediately paid
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "staff": st.session_state.user_role
                }
                
                # Save order and update customer
                orders_df = load_db("orders")
                orders_df = orders_df.append(new_order, ignore_index=True)
                save_db("orders", orders_df)
                
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
                st.write(f"Mobile: {customer['mobile']}")
                st.write(f"Total Orders: {customer['order_count']}")
                st.write(f"Total Spent: ₹{customer['total_spent']}")
                st.write(f"Loyalty Points: {customer['loyalty_points']}")
                st.write(f"Last Order: {customer['last_order']}")
                
                # Credit management
                st.subheader("Credit Management")
                current_balance = customer['credit_balance']
                st.write(f"Current Balance: ₹{current_balance}")
                
                col1, col2 = st.columns(2)
                with col1:
                    payment_amount = st.number_input("Payment Amount", min_value=0, max_value=current_balance)
                    if st.button("Record Payment") and payment_amount > 0:
                        # Update customer balance
                        customers_df = load_db("customers")
                        idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                        customers_df.at[idx, 'credit_balance'] -= payment_amount
                        save_db("customers", customers_df)
                        
                        # Record transaction
                        credit_df = load_db("credit")
                        credit_df = credit_df.append({
                            "mobile": search_mobile,
                            "amount": payment_amount,
                            "type": "payment",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "staff": st.session_state.user_role
                        }, ignore_index=True)
                        save_db("credit", credit_df)
                        st.success("Payment recorded!")
                        st.rerun()
                
                with col2:
                    credit_amount = st.number_input("Credit Amount", min_value=0)
                    if st.button("Add Credit") and credit_amount > 0:
                        # Update customer balance
                        customers_df = load_db("customers")
                        idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                        customers_df.at[idx, 'credit_balance'] += credit_amount
                        save_db("customers", customers_df)
                        
                        # Record transaction
                        credit_df = load_db("credit")
                        credit_df = credit_df.append({
                            "mobile": search_mobile,
                            "amount": credit_amount,
                            "type": "credit",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "staff": st.session_state.user_role
                        }, ignore_index=True)
                        save_db("credit", credit_df)
                        st.success("Credit added!")
                        st.rerun()
            else:
                st.warning("Customer not found")

    # Admin-only tabs
    if st.session_state.user_role == "Admin":
        with selected_tab[2]:  # Inventory
            st.header("📦 Inventory Management")
            # [Your inventory management code]
        
        with selected_tab[3]:  # Reports
            st.header("📊 Sales Reports")
            # [Your reporting code]
        
        with selected_tab[4]:  # Backup
            st.header("💾 System Backup")
            # [Your backup/restore code]

else:
    st.title("Momo Kiosk Pro")
    st.write("Please login from the sidebar to continue")
