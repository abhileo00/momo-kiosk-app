import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Configure page
st.set_page_config(
    page_title="Food Order System",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
<style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .order-card {
        border-left: 5px solid #4CAF50;
        padding: 15px;
        margin: 10px 0;
        background-color: #f9f9f9;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .total-display {
        font-size: 1.5em;
        font-weight: bold;
        color: #2E86C1;
        padding: 10px;
        background-color: #f0f8ff;
        border-radius: 5px;
    }
    .header {
        color: #2E86C1;
        border-bottom: 2px solid #4CAF50;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# MENU CONFIGURATION
MENU = {
    "Momos": {
        "Veg Half (6 pcs)": {"price": 80, "cost": 10},
        "Veg Full (12 pcs)": {"price": 150, "cost": 20},
        "Chicken Half (6 pcs)": {"price": 100, "cost": 17},
        "Chicken Full (12 pcs)": {"price": 190, "cost": 34}
    },
    "Sandwich": {
        "Veg Sandwich": {"price": 60, "cost": 15},
        "Cheese Veg Sandwich": {"price": 80, "cost": 25},
        "Chicken Sandwich": {"price": 100, "cost": 30}
    },
    "Maggi": {
        "Plain Maggi": {"price": 40, "cost": 10},
        "Veg Maggi": {"price": 60, "cost": 20},
        "Cheese Maggi": {"price": 70, "cost": 25},
        "Chicken Maggi": {"price": 90, "cost": 30}
    }
}

TOPPINGS = {
    "Extra Cheese": 20,
    "Masala": 10,
    "Butter": 10,
    "Egg": 15
}

# Initialize session state
if "orders" not in st.session_state:
    st.session_state.orders = []
if "customer_name" not in st.session_state:
    st.session_state.customer_name = ""

# App Header
st.markdown("<h1 class='header'>Food Order System</h1>", unsafe_allow_html=True)
st.markdown("---")

# Customer Section
with st.expander("Customer Information", expanded=True):
    customer_name = st.text_input(
        "Customer Name (required for credit)",
        value=st.session_state.customer_name,
        key="customer_input",
        placeholder="Enter customer name"
    )
    st.session_state.customer_name = customer_name

# Menu Section
with st.expander("Menu Selection", expanded=True):
    category = st.selectbox("Select Category", list(MENU.keys()))
    
    # Display menu items in columns
    cols = st.columns(2)
    for i, (item, details) in enumerate(MENU[category].items()):
        with cols[i % 2]:
            with st.container():
                st.markdown(f"#### {item}")
                st.markdown(f"Price: ₹{details['price']}")
                qty = st.number_input(
                    f"Quantity",
                    min_value=0,
                    step=1,
                    key=f"qty_{item}",
                    value=0
                )
                
                # Toppings selection
                add_toppings = []
                if category in ["Sandwich", "Maggi"] and qty > 0:
                    st.markdown("Add Toppings:")
                    for top_name, top_price in TOPPINGS.items():
                        if st.checkbox(
                            f"{top_name} (+₹{top_price})",
                            key=f"top_{item}_{top_name}"
                        ):
                            add_toppings.append((top_name, top_price))
                
                if st.button(f"Add to Order", key=f"btn_{item}"):
                    if qty > 0:
                        topping_names = ", ".join([t[0] for t in add_toppings])
                        total_price = (details["price"] + sum([t[1] for t in add_toppings])) * qty
                        total_cost = details["cost"] * qty
                        profit = total_price - total_cost

                        st.session_state.orders.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "customer": customer_name if customer_name else "Walk-in",
                            "category": category,
                            "item": item,
                            "qty": qty,
                            "toppings": topping_names,
                            "total_sale": total_price,
                            "total_cost": total_cost,
                            "profit": profit
                        })
                        st.success(f"Added {qty} × {item} to order!")
                        time.sleep(0.5)
                        st.rerun()

# Order Summary Section
st.markdown("---")
st.subheader("Current Order Summary")

if st.session_state.orders:
    df = pd.DataFrame(st.session_state.orders)
    
    # Display order items in cards
    for idx, order in enumerate(st.session_state.orders):
        with st.container():
            st.markdown(f"""
            <div class="order-card">
                <b>{order['item']}</b> × {order['qty']}<br>
                {f"<small>Toppings: {order['toppings']}</small>" if order['toppings'] else ""}<br>
                <b>Price:</b> ₹{order['total_sale']}
            </div>
            """, unsafe_allow_html=True)
    
    # Calculate totals
    total_sale = df["total_sale"].sum()
    total_profit = df["profit"].sum()
    
    st.markdown(f"""
    <div class="total-display">
        Total: ₹{total_sale} | Profit: ₹{total_profit}
    </div>
    """, unsafe_allow_html=True)
    
    # Payment options
    payment_col1, payment_col2 = st.columns([1, 2])
    with payment_col1:
        payment_mode = st.radio(
            "Payment Mode",
            ["Cash", "Credit"],
            index=0
        )
    
    # Submit and Clear buttons
    with payment_col2:
        submit_col, clear_col = st.columns(2)
        with submit_col:
            if st.button("Submit Order", type="primary"):
                if payment_mode == "Credit" and not customer_name:
                    st.error("Customer name is required for credit orders!")
                else:
                    try:
                        # Save to orders file
                        df.to_csv("orders.csv", index=False, mode='a', header=not pd.io.common.file_exists("orders.csv"))
                        
                        # Save to credit log if credit payment
                        if payment_mode == "Credit" and customer_name:
                            credit_df = df[["timestamp", "customer", "total_sale"]].rename(columns={"total_sale": "amount"})
                            credit_df.to_csv("credit_log.csv", index=False, mode='a', header=not pd.io.common.file_exists("credit_log.csv"))
                            st.warning(f"₹{total_sale} added to credit for {customer_name}")
                        
                        st.success("Order submitted successfully!")
                        st.session_state.orders = []
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving order: {str(e)}")
        
        with clear_col:
            if st.button("Clear Order"):
                st.session_state.orders = []
                st.rerun()
else:
    st.info("No items in current order. Add items from the menu above.")

# Admin Section
with st.sidebar:
    st.markdown("<h2 class='header'>Admin Panel</h2>", unsafe_allow_html=True)
    admin_pass = st.text_input("Enter Password", type="password")
    
    if admin_pass == "admin123":
        st.success("Admin access granted")
        
        if st.button("View Today's Orders"):
            try:
                df_all = pd.read_csv("orders.csv")
                df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
                df_all["date"] = df_all["timestamp"].dt.date
                today = datetime.now().date()
                df_today = df_all[df_all["date"] == today]
                
                if not df_today.empty:
                    st.dataframe(
                        df_today[["timestamp", "customer", "category", "item", "qty", "toppings", "total_sale", "profit"]],
                        use_container_width=True
                    )
                    st.markdown(f"""
                    Today's Summary  
                    Total Sales: ₹{df_today['total_sale'].sum()}  
                    Total Profit: ₹{df_today['profit'].sum()}  
                    Customers: {df_today['customer'].nunique()}
                    """)
                else:
                    st.info("No orders found for today.")
            except:
                st.error("No orders file found or error reading data.")
        
        if st.button("View Credit Balances"):
            try:
                credit_df = pd.read_csv("credit_log.csv")
                if not credit_df.empty:
                    balance_df = credit_df.groupby("customer")["amount"].sum().reset_index()
                    balance_df = balance_df.rename(columns={"amount": "Outstanding Balance (₹)"})
                    st.dataframe(balance_df, use_container_width=True)
                    st.markdown(f"Total Outstanding: ₹{balance_df['Outstanding Balance (₹)'].sum()}")
                else:
                    st.info("No credit data found.")
            except:
                st.error("No credit log file found or error reading data.")
    elif admin_pass:
        st.error("Incorrect password")
