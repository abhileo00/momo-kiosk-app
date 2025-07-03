import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import shutil
import re

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
            customers_df.at[idx, 'loyalty_points'] += int(amount / 10)
            
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

# Login Page
if not st.session_state.user_role:
    st.title("Momo Kiosk Pro - Login")
    
    with st.form("login_form"):
        role = st.selectbox("Select Role", ["Staff", "Admin"])
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            # Simple authentication
            if (role == "Staff" and password == "staff123") or \
               (role == "Admin" and password == "admin123"):
                st.session_state.user_role = role
                st.rerun()
            else:
                st.error("Invalid credentials")

# Main App
else:
    tabs = ["📝 Order", "👥 Customers"]
    if st.session_state.user_role == "Admin":
        tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])
    
    selected_tab = st.tabs(tabs)

    # Order Tab
    with selected_tab[0]:
        st.header("📝 New Order")
        
        # Customer Information
        mobile = st.text_input("Mobile Number (Required)", key="order_mobile")
        mobile_valid = re.match(r'^[6-9]\d{9}$', mobile) if mobile else False
        
        if mobile and not mobile_valid:
            st.error("Please enter a valid 10-digit Indian mobile number")
        
        customer_name = st.text_input("Customer Name (Optional)", key="customer_name")
        
        # Payment Section
        payment_method = st.radio("Payment Method:", 
                                ["Cash", "Credit"], 
                                horizontal=True,
                                key="payment_method")
        
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
        
        total_amount = calculate_total(order_items)
        st.subheader(f"Total Amount: ₹{total_amount}")
        
        # Credit payment validation
        if payment_method == "Credit":
            if not mobile:
                st.warning("Mobile number required for credit payments")
            elif mobile and not mobile_valid:
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
            if not mobile:
                st.error("Mobile number is required for all orders")
            elif not mobile_valid:
                st.error("Please enter a valid mobile number")
            elif not order_items:
                st.error("Please add at least one item to the order")
            elif payment_method == "Credit" and mobile and mobile_valid:
                customer = get_customer(mobile)
                if customer and customer['credit_balance'] < total_amount:
                    st.error("Customer has insufficient credit balance")
                else:
                    # Process the order
                    update_customer(
                        mobile=mobile,
                        name=customer_name,
                        amount=total_amount,
                        order_placed=True
                    )
                    
                    new_order = {
                        "order_id": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "mobile": mobile,
                        "items": str(order_items),
                        "total": total_amount,
                        "payment_method": payment_method,
                        "paid": payment_method == "Cash",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "staff": st.session_state.user_role
                    }
                    
                    orders_df = load_db("orders")
                    orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                    save_db("orders", orders_df)
                    
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
            else:
                # Process cash order
                update_customer(
                    mobile=mobile,
                    name=customer_name,
                    amount=total_amount,
                    order_placed=True
                )
                
                new_order = {
                    "order_id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "mobile": mobile,
                    "items": str(order_items),
                    "total": total_amount,
                    "payment_method": payment_method,
                    "paid": True,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "staff": st.session_state.user_role
                }
                
                orders_df = load_db("orders")
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
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

    # Customers Tab (remaining code stays exactly the same)
    with selected_tab[1]:
        st.header("👥 Customer Management")
        
        search_mobile = st.text_input("Search by Mobile Number")
        if search_mobile:
            customer = get_customer(search_mobile)
            if customer:
                # ... [rest of customer management code remains unchanged] ...

    # Admin tabs (remaining code stays exactly the same)
    if st.session_state.user_role == "Admin":
        with selected_tab[2]:  # Inventory
            st.header("📦 Inventory Management")
            st.write("Inventory management coming soon!")
        
        with selected_tab[3]:  # Reports
            st.header("📊 Sales Reports")
            # ... [rest of reports code remains unchanged] ...
        
        with selected_tab[4]:  # Backup
            st.header("💾 System Backup")
            # ... [rest of backup code remains unchanged] ...
