
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Momo Kiosk", layout="wide")

# -----------------------
# MENU CONFIGURATION
# -----------------------

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

# -----------------------
# SESSION STATE
# -----------------------

if "orders" not in st.session_state:
    st.session_state.orders = []

st.title("🥟 Momo & Snacks Kiosk")
st.markdown("### Tap to place an order")

# -----------------------
# CATEGORY SELECTION
# -----------------------

category = st.selectbox("Select Category", list(MENU.keys()))

st.markdown("### Menu Items")
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
            topping_total = sum([t[1] for t in add_toppings]) * qty
            total_price = (details["price"] + sum([t[1] for t in add_toppings])) * qty
            total_cost = details["cost"] * qty
            profit = total_price - total_cost

            st.session_state.orders.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "category": category,
                "item": item,
                "qty": qty,
                "toppings": topping_names,
                "total_sale": total_price,
                "total_cost": total_cost,
                "profit": profit
            })
            st.success(f"Added {qty} × {item} with toppings: {topping_names if topping_names else 'None'}")

# -----------------------
# ORDER SUMMARY
# -----------------------

st.markdown("---")
st.subheader("🧾 Current Order Summary")

if st.session_state.orders:
    df = pd.DataFrame(st.session_state.orders)
    st.dataframe(df[["timestamp", "category", "item", "qty", "toppings", "total_sale", "profit"]], use_container_width=True)

    total_sale = df["total_sale"].sum()
    total_profit = df["profit"].sum()
    st.markdown(f"### 💵 Total Sale: ₹{total_sale} | 💰 Profit: ₹{total_profit}")

    if st.button("✅ Submit Orders & Save"):
        df.to_csv("orders.csv", index=False, mode='a', header=False)
        st.success("Orders saved to orders.csv!")
        st.session_state.orders = []
else:
    st.info("No orders placed yet.")
