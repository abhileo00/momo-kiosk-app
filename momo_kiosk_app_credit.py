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
    },
    "Thali": {
        "Veg Thali": {"price": 70, "cost": 25},
        "Non-Veg Thali": {"price": 100, "cost": 40}
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
if "order_counter" not in st.session_state:
    st.session_state.order_counter = 1

st.title("🥟 Momo & Snacks Kiosk")
st.markdown("### Tap to place an order")

# -----------------------
# CATEGORY SELECTION - Using Tabs for better UX
# -----------------------

tab1, tab2, tab3, tab4 = st.tabs(["Momos", "Sandwich", "Maggi", "Thali"])

def display_category(category):
    st.markdown(f"### {category} Menu")
    cols = st.columns(2)
    
    for i, (item, details) in enumerate(MENU[category].items()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{item}** - ₹{details['price']}")
                qty = st.number_input(f"Quantity", min_value=0, max_value=20, step=1, key=f"qty_{category}_{item}")
                add_toppings = []

                # Only show toppings for Sandwich and Maggi
                if category in ["Sandwich", "Maggi"] and qty > 0:
                    st.markdown("**Add Toppings:**")
                    for top_name, top_price in TOPPINGS.items():
                        if st.checkbox(f"{top_name} (+₹{top_price})", key=f"top_{category}_{item}_{top_name}"):
                            add_toppings.append((top_name, top_price))

                if st.button(f"Add to Order", key=f"btn_{category}_{item}", use_container_width=True):
                    if qty > 0:
                        topping_names = ", ".join([t[0] for t in add_toppings]) if add_toppings else "None"
                        topping_total = sum([t[1] for t in add_toppings]) * qty
                        total_price = (details["price"] + sum([t[1] for t in add_toppings])) * qty
                        total_cost = details["cost"] * qty
                        profit = total_price - total_cost

                        st.session_state.orders.append({
                            "order_id": st.session_state.order_counter,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "category": category,
                            "item": item,
                            "qty": qty,
                            "toppings": topping_names,
                            "total_sale": total_price,
                            "total_cost": total_cost,
                            "profit": profit
                        })
                        st.success(f"Added {qty} × {item} with toppings: {topping_names}")
                        st.session_state.order_counter += 1
                    else:
                        st.warning("Please select a quantity greater than 0")

with tab1:
    display_category("Momos")

with tab2:
    display_category("Sandwich")

with tab3:
    display_category("Maggi")

with tab4:
    display_category("Thali")

# -----------------------
# ORDER SUMMARY
# -----------------------

st.markdown("---")
st.subheader("🧾 Current Order Summary")

if st.session_state.orders:
    df = pd.DataFrame(st.session_state.orders)
    
    # Display editable dataframe
    edited_df = st.data_editor(
        df[["order_id", "category", "item", "qty", "toppings", "total_sale"]],
        use_container_width=True,
        num_rows="dynamic"
    )
    
    # Calculate totals
    total_sale = df["total_sale"].sum()
    total_profit = df["profit"].sum()
    st.markdown(f"### 💵 Total Sale: ₹{total_sale} | 💰 Profit: ₹{total_profit}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Submit Orders & Save", use_container_width=True):
            try:
                df.to_csv("orders.csv", index=False, mode='a', header=not pd.io.common.file_exists("orders.csv"))
                st.success("Orders saved to orders.csv!")
                st.session_state.orders = []
                st.session_state.order_counter = 1
                st.rerun()
            except Exception as e:
                st.error(f"Error saving orders: {e}")
    
    with col2:
        if st.button("❌ Clear All Orders", use_container_width=True):
            st.session_state.orders = []
            st.rerun()
else:
    st.info("No orders placed yet.")
