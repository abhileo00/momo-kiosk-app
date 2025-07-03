
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import shutil
import time

# ----------------------
# CONFIGURATION
# ----------------------
APP_NAME = "Food Hub"
DATA_FOLDER = "food_hub_data/"
BACKUP_FOLDER = os.path.join(DATA_FOLDER, "backups")
PASSWORDS = {"Admin": "admin123", "Staff": "staff123"}

DATABASES = {
    "orders": os.path.join(DATA_FOLDER, "orders.csv"),
    "credit": os.path.join(DATA_FOLDER, "credit_log.csv"),
    "inventory": os.path.join(DATA_FOLDER, "inventory.csv")
}

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

# ----------------------
# INITIALIZATION
# ----------------------
def init_data():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(BACKUP_FOLDER, exist_ok=True)
    for path in DATABASES.values():
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("")

init_data()

st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)

if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "orders" not in st.session_state:
    st.session_state.orders = []

# ----------------------
# LOGIN SIDEBAR
# ----------------------
with st.sidebar:
    st.title("Login")
    if not st.session_state.authenticated:
        role = st.selectbox("Select Role", ["Admin", "Staff"])
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if PASSWORDS.get(role) == password:
                st.session_state.user_role = role
                st.session_state.authenticated = True
                st.success(f"Logged in as {role}")
                st.rerun()
            else:
                st.error("Incorrect password")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.rerun()

        if st.session_state.user_role == "Admin":
            st.markdown("---")
            if st.button("View Today's Orders"):
                try:
                    df_all = pd.read_csv(DATABASES["orders"])
                    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
                    df_all["date"] = df_all["timestamp"].dt.date
                    today = datetime.now().date()
                    df_today = df_all[df_all["date"] == today]
                    st.dataframe(df_today[["timestamp", "customer", "category", "item", "qty", "toppings", "total_sale", "profit"]])
                    st.markdown(f"Total Sale: ₹{df_today['total_sale'].sum()} | Profit: ₹{df_today['profit'].sum()}")
                except:
                    st.error("No orders found.")

            if st.button("View Credit Balances"):
                try:
                    credit_df = pd.read_csv(DATABASES["credit"])
                    summary = credit_df.groupby("customer")["amount"].sum().reset_index().rename(columns={"amount": "Outstanding ₹"})
                    st.dataframe(summary)
                except:
                    st.error("No credit data found.")

# ----------------------
# MAIN ORDER PAGE
# ----------------------
if st.session_state.authenticated:
    st.subheader("Place an Order")
    customer = st.text_input("Customer Name (optional)", placeholder="Enter name for credit or tracking")
    category = st.selectbox("Select Category", list(MENU.keys()))

    for item, details in MENU[category].items():
        st.markdown(f"**{item}** - ₹{details['price']}")
        qty = st.number_input(f"Qty for {item}", min_value=0, step=1, key=f"qty_{item}")
        add_toppings = []

        if category in ["Sandwich", "Maggi"] and qty > 0:
            st.markdown("**Add Toppings:**")
            cols = st.columns(4)
            for i, (top_name, top_price) in enumerate(TOPPINGS.items()):
                with cols[i % 4]:
                    if st.checkbox(f"{top_name} (+₹{top_price})", key=f"top_{item}_{top_name}"):
                        add_toppings.append((top_name, top_price))

        if st.button(f"Add {item}", key=f"btn_{item}"):
            if qty > 0:
                topping_names = ", ".join([t[0] for t in add_toppings])
                total_price = (details["price"] + sum([t[1] for t in add_toppings])) * qty
                total_cost = details["cost"] * qty
                profit = total_price - total_cost

                st.session_state.orders.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "customer": customer if customer else "Walk-in",
                    "category": category,
                    "item": item,
                    "qty": qty,
                    "toppings": topping_names,
                    "total_sale": total_price,
                    "total_cost": total_cost,
                    "profit": profit
                })
                st.success(f"Added {qty} × {item} {'for ' + customer if customer else ''}")

    st.markdown("---")
    st.subheader("Current Order Summary")

    if st.session_state.orders:
        df = pd.DataFrame(st.session_state.orders)
        st.dataframe(df[["timestamp", "customer", "category", "item", "qty", "toppings", "total_sale", "profit"]])
        total_sale = df["total_sale"].sum()
        total_profit = df["profit"].sum()
        st.markdown(f"### Total: ₹{total_sale} | Profit: ₹{total_profit}")

        payment_mode = st.radio("Payment Mode", ["Paid", "Credit"])

        if st.button("Submit & Save Order"):
            df.to_csv(DATABASES["orders"], index=False, mode='a', header=not os.path.exists(DATABASES["orders"]))
            if payment_mode == "Credit" and customer:
                credit_df = df[["timestamp", "customer", "total_sale"]].rename(columns={"total_sale": "amount"})
                credit_df.to_csv(DATABASES["credit"], index=False, mode='a', header=not os.path.exists(DATABASES["credit"]))
                st.warning(f"₹{total_sale} added to credit for {customer}")
            st.success("Order saved successfully!")
            st.session_state.orders = []
    else:
        st.info("No orders yet.")
else:
    st.warning("Please log in using the sidebar to use the app.")
