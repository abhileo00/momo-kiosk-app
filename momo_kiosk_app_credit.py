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

# ... [keep previous constants and functions until the Streamlit app section] ...

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
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image("https://via.placeholder.com/150", width=150)  # Replace with your logo
    with col2:
        st.subheader("Staff Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Staff", "Admin"])
        
        if st.form_submit_button("Login"):
            # Simple authentication - replace with proper auth in production
            if (role == "Staff" and password == "staff123") or \
               (role == "Admin" and password == "admin123"):
                st.session_state.user_role = role
                st.rerun()
            else:
                st.error("Invalid credentials")

# Main App
else:
    # Tabs setup based on role
    tabs = ["📝 Order", "👥 Customers"]
    if st.session_state.user_role == "Admin":
        tabs.extend(["📦 Inventory", "📊 Reports", "💾 Backup"])
    
    selected_tab = st.tabs(tabs)

    # Order Tab
    with selected_tab[0]:
        st.header("📝 New Order")
        
        # Customer Information
        mobile = st.text_input("Mobile Number (Required)", key="order_mobile")
        
        # Validate mobile number format (10 digits for India)
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
        
        # Calculate total
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
        
        # Place order button with validation
        if st.button("Place Order"):
            # Validate required fields
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
                    # Process the order (same as before)
                    process_order(mobile, customer_name, payment_method, order_items, total_amount)
            else:
                # Process cash order
                process_order(mobile, customer_name, payment_method, order_items, total_amount)

def process_order(mobile, name, payment_method, order_items, total_amount):
    """Helper function to process orders"""
    # Update customer
    update_customer(
        mobile=mobile,
        name=name,
        amount=total_amount,
        order_placed=True
    )
    
    # Record transaction
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
    st.balloons()
    st.session_state.current_order = {
        "items": [],
        "customer_mobile": "",
        "customer_name": "",
        "payment_method": "Cash",
        "paid": False
    }
    st.rerun()

# ... [rest of the code remains the same] ...
