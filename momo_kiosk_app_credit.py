import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import shutil
import re
import ast

# ======================
# DATA CONFIGURATION
# ======================
DATA_FOLDER = "chai_snacks_data/"
DATABASES = {
    "orders": DATA_FOLDER + "orders.csv",
    "menu": DATA_FOLDER + "menu.csv",
    "customers": DATA_FOLDER + "customers.csv",
    "credit": DATA_FOLDER + "credit_transactions.csv",
    "inventory": DATA_FOLDER + "inventory.csv",
    "food_items": DATA_FOLDER + "food_items.csv"
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

DEFAULT_FOOD_ITEMS = {
    "Masala Chai": {"price": 20, "category": "Beverage", "stock": 100},
    "Ginger Tea": {"price": 20, "category": "Beverage", "stock": 100},
    "Filter Coffee": {"price": 25, "category": "Beverage", "stock": 80},
    "Samosa": {"price": 25, "category": "Snack", "stock": 50},
    "Vada Pav": {"price": 30, "category": "Snack", "stock": 40},
    "Sandwich": {"price": 60, "category": "Lunch", "stock": 30},
    "Veg Thali": {"price": 120, "category": "Lunch", "stock": 20},
    "Chicken Thali": {"price": 150, "category": "Lunch", "stock": 20},
    "Gulab Jamun": {"price": 40, "category": "Dessert", "stock": 30}
}

# ======================
# DATA MANAGEMENT
# ======================
def init_data_system():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        os.makedirs(DATA_FOLDER + "backups/")

    # Initialize food items database
    if not os.path.exists(DATABASES["food_items"]):
        food_df = pd.DataFrame.from_dict(DEFAULT_FOOD_ITEMS, orient='index').reset_index()
        food_df = food_df.rename(columns={'index': 'item'})
        food_df.to_csv(DATABASES["food_items"], index=False)

    # Initialize menu database from food items
    if not os.path.exists(DATABASES["menu"]):
        food_df = pd.read_csv(DATABASES["food_items"])
        menu_df = food_df[['item', 'price', 'category']]
        menu_df.to_csv(DATABASES["menu"], index=False)

    # Initialize other databases
    for db_name, db_path in DATABASES.items():
        if not os.path.exists(db_path) and db_name not in ["food_items", "menu"]:
            pd.DataFrame().to_csv(db_path, index=False)

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
        idx = customers_df[customers_df['mobile'] == mobile].index[0]
        
        if order_placed:
            customers_df.at[idx, 'order_count'] += 1
            customers_df.at[idx, 'total_spent'] += amount
            customers_df.at[idx, 'last_order'] = datetime.now().strftime('%Y-%m-%d')
            customers_df.at[idx, 'loyalty_points'] += int(amount / 10)
            
        if name:
            customers_df.at[idx, 'name'] = name
    else:
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
        if os.path.exists(db_file):
            shutil.copy2(db_file, backup_folder)
    return backup_folder

def get_food_items():
    try:
        return pd.read_csv(DATABASES["food_items"])
    except:
        return pd.DataFrame()

def add_food_item(name, price, category, stock):
    food_df = get_food_items()
    new_item = pd.DataFrame([{
        "item": name,
        "price": price,
        "category": category,
        "stock": stock
    }])
    food_df = pd.concat([food_df, new_item], ignore_index=True)
    food_df.to_csv(DATABASES["food_items"], index=False)
    # Update menu automatically
    menu_df = food_df[['item', 'price', 'category']]
    menu_df.to_csv(DATABASES["menu"], index=False)

def update_stock(item_name, quantity_change):
    food_df = get_food_items()
    if not food_df.empty and item_name in food_df['item'].values:
        idx = food_df[food_df['item'] == item_name].index[0]
        food_df.at[idx, 'stock'] += quantity_change
        food_df.to_csv(DATABASES["food_items"], index=False)

# ======================
# STREAMLIT APP
# ======================
st.set_page_config(page_title="Chai Snacks Lunch Hub", layout="wide")
init_data_system()

# Initialize session state
if "user_role" not in st.session_state:
    st.session_state.user_role = None
    st.session_state.authenticated = False
    st.session_state.username = None

if "current_order" not in st.session_state:
    st.session_state.current_order = {
        "items": [],
        "customer_mobile": "",
        "customer_name": "",
        "payment_method": "Cash",
        "paid": False
    }

# Authentication
VALID_USERS = {
    "staff": {
        "password": "staff123",
        "role": "Staff"
    },
    "admin": {
        "password": "admin123",
        "role": "Admin"
    }
}

# Login Page
if not st.session_state.authenticated:
    st.title("Chai Snacks Lunch Hub - Login")
    
    login_tab, help_tab = st.tabs(["Login", "Help"])
    
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username").strip().lower()
            password = st.text_input("Password", type="password").strip()
            
            if st.form_submit_button("Login"):
                if username in VALID_USERS:
                    if password == VALID_USERS[username]["password"]:
                        st.session_state.user_role = VALID_USERS[username]["role"]
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("❌ Incorrect password")
                else:
                    st.error("❌ Username not found")
    
    with help_tab:
        st.markdown("### Login Help")
        st.write("Use these test credentials:")
        st.write("- **Staff Login**:")
        st.code("Username: staff\nPassword: staff123")
        st.write("- **Admin Login**:")
        st.code("Username: admin\nPassword: admin123")
    
    st.stop()

# Main App
st.sidebar.title(f"Chai Snacks Lunch Hub")
st.sidebar.subheader(f"Logged in as {st.session_state.username} ({st.session_state.user_role})")

if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

# Tabs setup
tabs = ["📝 Order", "👥 Customers"]
if st.session_state.user_role == "Admin":
    tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])

selected_tab = st.tabs(tabs)

# Order Tab
with selected_tab[0]:
    st.header("📝 New Order")
    
    # Payment Method Selection
    payment_method = st.radio("Payment Method:", 
                            ["Cash", "Credit"], 
                            horizontal=True,
                            key="payment_method")
    
    # Customer Information
    if payment_method == "Credit":
        mobile = st.text_input("Mobile Number (Required for Credit)", key="order_mobile")
        mobile_valid = re.match(r'^[6-9]\d{9}$', mobile) if mobile else False
        if mobile and not mobile_valid:
            st.error("Please enter a valid 10-digit Indian mobile number")
    else:
        mobile = st.text_input("Mobile Number (Optional)", key="order_mobile")
        mobile_valid = True if not mobile else re.match(r'^[6-9]\d{9}$', mobile)
    
    customer_name = st.text_input("Customer Name (Optional)", key="customer_name")
    
    # Menu Selection
    st.subheader("Menu Items")
    menu_df = load_db("menu")
    food_df = get_food_items()
    
    # Merge menu with stock information
    menu_df = menu_df.merge(food_df[['item', 'stock']], on='item', how='left')
    
    order_items = []
    for _, item in menu_df.iterrows():
        with st.expander(f"{item['item']} - ₹{item['price']} ({item['stock']} available)"):
            max_quantity = min(10, item['stock']) if not pd.isna(item['stock']) else 10
            quantity = st.number_input(f"Quantity", 
                                     min_value=0, 
                                     max_value=max_quantity, 
                                     key=f"qty_{item['item']}")
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
    
    total_amount = calculate_total(order_items) if order_items else 0
    st.subheader(f"Total Amount: ₹{total_amount}")
    
    # Credit payment validation
    if payment_method == "Credit":
        if not mobile:
            st.warning("Mobile number required for credit payments")
        elif not mobile_valid:
            st.error("Valid mobile number required for credit payments")
        else:
            customer = get_customer(mobile)
            if customer:
                st.info(f"Customer: {customer.get('name', '')} | Balance: ₹{customer.get('credit_balance', 0)}")
                if customer['credit_balance'] < total_amount:
                    st.error("Insufficient credit balance")
            else:
                st.info("New customer will be registered for credit payments")
    
    if st.button("Place Order"):
        if not order_items:
            st.error("Please add at least one item to the order")
        elif payment_method == "Credit":
            if not mobile:
                st.error("Mobile number is required for credit payments")
            elif not mobile_valid:
                st.error("Please enter a valid mobile number")
            else:
                customer = get_customer(mobile)
                if customer and customer['credit_balance'] < total_amount:
                    st.error("Customer has insufficient credit balance")
                else:
                    # Process credit order
                    update_customer(
                        mobile=mobile,
                        name=customer_name,
                        amount=total_amount,
                        order_placed=True
                    )
                    
                    # Update stock
                    for item in order_items:
                        update_stock(item['item'], -item['quantity'])
                    
                    new_order = {
                        "order_id": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "mobile": mobile,
                        "items": str(order_items),
                        "total": total_amount,
                        "payment_method": payment_method,
                        "paid": False,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "staff": st.session_state.username
                    }
                    
                    # Record credit transaction
                    credit_df = load_db("credit")
                    credit_df = pd.concat([credit_df, pd.DataFrame([{
                        "mobile": mobile,
                        "amount": total_amount,
                        "type": "purchase",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "staff": st.session_state.username
                    }])], ignore_index=True)
                    save_db("credit", credit_df)
                    
                    # Save order
                    orders_df = load_db("orders")
                    orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                    save_db("orders", orders_df)
                    
                    # Update customer balance
                    if customer:
                        customers_df = load_db("customers")
                        idx = customers_df[customers_df['mobile'] == mobile].index[0]
                        customers_df.at[idx, 'credit_balance'] -= total_amount
                        save_db("customers", customers_df)
                    
                    st.success("Credit order placed successfully!")
                    st.balloons()
                    st.session_state.current_order = {
                        "items": [],
                        "customer_mobile": "",
                        "customer_name": "",
                        "payment_method": "Cash",
                        "paid": False
                    }
                    st.rerun()
        else:
            # Process cash order
            if mobile:  # Only update customer if mobile provided
                update_customer(
                    mobile=mobile,
                    name=customer_name,
                    amount=total_amount,
                    order_placed=True
                )
            
            # Update stock
            for item in order_items:
                update_stock(item['item'], -item['quantity'])
            
            new_order = {
                "order_id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "mobile": mobile if mobile else "",
                "items": str(order_items),
                "total": total_amount,
                "payment_method": payment_method,
                "paid": True,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "staff": st.session_state.username
            }
            
            orders_df = load_db("orders")
            orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
            save_db("orders", orders_df)
            
            st.success("Cash order placed successfully!")
            st.balloons()
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
            
            st.subheader("Credit Management")
            current_balance = customer['credit_balance']
            st.write(f"Current Balance: ₹{current_balance}")
            
            col1, col2 = st.columns(2)
            with col1:
                with st.form("payment_form"):
                    payment_amount = st.number_input("Payment Amount", 
                                                   min_value=0, 
                                                   max_value=current_balance, 
                                                   value=0)
                    if st.form_submit_button("Record Payment") and payment_amount > 0:
                        customers_df = load_db("customers")
                        idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                        customers_df.at[idx, 'credit_balance'] -= payment_amount
                        save_db("customers", customers_df)
                        
                        credit_df = load_db("credit")
                        credit_df = pd.concat([credit_df, pd.DataFrame([{
                            "mobile": search_mobile,
                            "amount": payment_amount,
                            "type": "payment",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "staff": st.session_state.username
                        }])], ignore_index=True)
                        save_db("credit", credit_df)
                        st.success("Payment recorded!")
                        st.rerun()
            
            with col2:
                with st.form("credit_form"):
                    credit_amount = st.number_input("Credit Amount", min_value=0, value=0)
                    if st.form_submit_button("Add Credit") and credit_amount > 0:
                        customers_df = load_db("customers")
                        idx = customers_df[customers_df['mobile'] == search_mobile].index[0]
                        customers_df.at[idx, 'credit_balance'] += credit_amount
                        save_db("customers", customers_df)
                        
                        credit_df = load_db("credit")
                        credit_df = pd.concat([credit_df, pd.DataFrame([{
                            "mobile": search_mobile,
                            "amount": credit_amount,
                            "type": "credit",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "staff": st.session_state.username
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
        
        tab1, tab2 = st.tabs(["View Inventory", "Add New Item"])
        
        with tab1:
            st.subheader("Current Food Items")
            food_df = get_food_items()
            if not food_df.empty:
                st.dataframe(food_df)
                
                # Stock management
                st.subheader("Update Stock")
                selected_item = st.selectbox("Select item to update", food_df['item'])
                current_stock = int(food_df[food_df['item'] == selec
