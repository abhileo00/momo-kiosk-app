import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import shutil
import csv

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

# ======================
# DATA MANAGEMENT FUNCTIONS
# ======================
def init_data_system():
    """Initialize all required data files and folders"""
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        os.makedirs(DATA_FOLDER + "backups/")
    
    # Create default menu if not exists
    if not os.path.exists(DATABASES["menu"]):
        default_menu = {
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
        save_menu_data(default_menu)

def load_db(db_name):
    """Load a database table"""
    try:
        return pd.read_csv(DATABASES[db_name])
    except:
        return pd.DataFrame()

def save_db(db_name, df):
    """Save a database table"""
    df.to_csv(DATABASES[db_name], index=False)

def load_menu():
    """Load menu data from database"""
    menu = {}
    df = load_db("menu")
    if not df.empty:
        for category in df['category'].unique():
            category_items = {}
            for _, row in df[df['category'] == category].iterrows():
                category_items[row['item']] = {
                    "price": row['price'],
                    "cost": row['cost']
                }
            menu[category] = category_items
    return menu

def save_menu_data(menu):
    """Save menu data to database"""
    rows = []
    for category, items in menu.items():
        for item, details in items.items():
            rows.append({
                "category": category,
                "item": item,
                "price": details["price"],
                "cost": details["cost"]
            })
    save_db("menu", pd.DataFrame(rows))

def create_backup():
    """Create a timestamped backup of all data"""
    backup_dir = f"{DATA_FOLDER}backups/{datetime.now().strftime('%Y-%m-%d_%H-%M')}/"
    os.makedirs(backup_dir, exist_ok=True)
    
    for db_name, db_path in DATABASES.items():
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_dir + db_name + ".csv")
    return backup_dir

def restore_backup(backup_date):
    """Restore data from a specific backup"""
    backup_dir = f"{DATA_FOLDER}backups/{backup_date}/"
    if os.path.exists(backup_dir):
        for db_name in DATABASES.keys():
            backup_path = backup_dir + db_name + ".csv"
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, DATABASES[db_name])
        return True
    return False

# ======================
# STREAMLIT APP
# ======================
st.set_page_config(page_title="Momo Kiosk Pro", layout="wide")
init_data_system()

# Initialize session state
if "orders" not in st.session_state:
    st.session_state.orders = []
if "order_counter" not in st.session_state:
    st.session_state.order_counter = 1
if "menu" not in st.session_state:
    st.session_state.menu = load_menu()

# Main app tabs
tab_order, tab_inventory, tab_customers, tab_reports, tab_backup = st.tabs([
    "📝 Order", "📦 Inventory", "👥 Customers", "📊 Reports", "💾 Backup"
])

# ======================
# ORDER TAB
# ======================
with tab_order:
    st.title("🥟 Momo Kiosk Pro")
    st.markdown("### Place New Order")
    
    # Category selection
    category = st.selectbox("Select Category", list(st.session_state.menu.keys()))
    
    # Menu items display
    st.markdown(f"### {category} Menu")
    cols = st.columns(2)
    
    for i, (item, details) in enumerate(st.session_state.menu[category].items()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{item}** - ₹{details['price']}")
                qty = st.number_input(f"Quantity", min_value=0, max_value=20, step=1, key=f"qty_{category}_{item}")
                add_toppings = []

                if category in ["Sandwich", "Maggi"] and qty > 0:
                    st.markdown("**Add Toppings:**")
                    for top_name, top_price in TOPPINGS.items():
                        if st.checkbox(f"{top_name} (+₹{top_price})", key=f"top_{category}_{item}_{top_name}"):
                            add_toppings.append((top_name, top_price))

                if st.button(f"Add to Order", key=f"btn_{category}_{item}", use_container_width=True):
                    if qty > 0:
                        topping_names = ", ".join([t[0] for t in add_toppings]) if add_toppings else "None"
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

    # Order summary
    st.markdown("---")
    st.subheader("🧾 Current Order Summary")

    if st.session_state.orders:
        df = pd.DataFrame(st.session_state.orders)
        
        edited_df = st.data_editor(
            df[["order_id", "category", "item", "qty", "toppings", "total_sale"]],
            use_container_width=True,
            num_rows="dynamic"
        )
        
        total_sale = df["total_sale"].sum()
        total_profit = df["profit"].sum()
        st.markdown(f"### 💵 Total Sale: ₹{total_sale} | 💰 Profit: ₹{total_profit}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Submit Orders & Save", use_container_width=True):
                try:
                    # Append to orders file
                    if not os.path.exists(DATABASES["orders"]):
                        df.to_csv(DATABASES["orders"], index=False)
                    else:
                        df.to_csv(DATABASES["orders"], mode='a', header=False, index=False)
                    
                    st.success("Orders saved successfully!")
                    st.session_state.orders = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving orders: {e}")
        
        with col2:
            if st.button("❌ Clear All Orders", use_container_width=True):
                st.session_state.orders = []
                st.rerun()
    else:
        st.info("No orders placed yet.")

# ======================
# INVENTORY TAB
# ======================
with tab_inventory:
    st.header("📦 Inventory Management")
    st.markdown("Edit item prices and costs below")
    
    # Create editable dataframe for inventory
    inventory_rows = []
    for category, items in st.session_state.menu.items():
        for item, details in items.items():
            inventory_rows.append({
                "Category": category,
                "Item": item,
                "Selling Price": details["price"],
                "Cost Price": details["cost"]
            })
    
    inventory_df = pd.DataFrame(inventory_rows)
    edited_inventory = st.data_editor(
        inventory_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Selling Price": st.column_config.NumberColumn("Selling Price (₹)"),
            "Cost Price": st.column_config.NumberColumn("Cost Price (₹)")
        }
    )
    
    if st.button("💾 Save Inventory Changes", use_container_width=True):
        # Update the menu data structure
        new_menu = {}
        for _, row in edited_inventory.iterrows():
            category = row["Category"]
            item = row["Item"]
            if category not in new_menu:
                new_menu[category] = {}
            new_menu[category][item] = {
                "price": row["Selling Price"],
                "cost": row["Cost Price"]
            }
        
        st.session_state.menu = new_menu
        save_menu_data(new_menu)
        st.success("Inventory updated successfully!")
        st.rerun()

# ======================
# CUSTOMERS TAB
# ======================
with tab_customers:
    st.header("👥 Customer Management")
    
    tab1, tab2 = st.tabs(["Customer Database", "Credit Transactions"])
    
    with tab1:
        st.subheader("Registered Customers")
        customers_df = load_db("customers")
        
        if customers_df.empty:
            customers_df = pd.DataFrame(columns=[
                "customer_id", "name", "phone", "address", 
                "credit_limit", "balance", "join_date"
            ])
        
        edited_customers = st.data_editor(
            customers_df,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        if st.button("Save Customer Data", use_container_width=True):
            save_db("customers", edited_customers)
            st.success("Customer data saved!")
    
    with tab2:
        st.subheader("Credit Transactions")
        credit_df = load_db("credit")
        
        if credit_df.empty:
            credit_df = pd.DataFrame(columns=[
                "transaction_id", "customer_id", "date", 
                "amount", "type", "description", "paid"
            ])
        
        edited_credit = st.data_editor(
            credit_df,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        if st.button("Save Credit Data", use_container_width=True):
            save_db("credit", edited_credit)
            st.success("Credit transactions saved!")

# ======================
# REPORTS TAB
# ======================
with tab_reports:
    st.header("📊 Sales Reports")
    
    report_date = st.date_input("Select date for report", date.today())
    report_type = st.selectbox("Report Type", ["Daily Summary", "Category-wise", "Item-wise"])
    
    if st.button("Generate Report", use_container_width=True):
        orders_df = load_db("orders")
        if orders_df.empty:
            st.warning("No order data available")
        else:
            orders_df['date'] = pd.to_datetime(orders_df['timestamp']).dt.date
            daily_orders = orders_df[orders_df['date'] == report_date]
            
            if daily_orders.empty:
                st.warning(f"No orders found for {report_date}")
            else:
                st.subheader(f"📅 Sales Report for {report_date}")
                
                total_sale = daily_orders['total_sale'].sum()
                total_cost = daily_orders['total_cost'].sum()
                total_profit = daily_orders['profit'].sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Sales", f"₹{total_sale}")
                col2.metric("Total Cost", f"₹{total_cost}")
                col3.metric("Total Profit", f"₹{total_profit}")
                
                if report_type == "Category-wise":
                    st.subheader("Category Breakdown")
                    category_sales = daily_orders.groupby('category').agg({
                        'qty': 'sum',
                        'total_sale': 'sum',
                        'profit': 'sum'
                    }).reset_index()
                    st.dataframe(category_sales, use_container_width=True)
                
                elif report_type == "Item-wise":
                    st.subheader("Item Breakdown")
                    item_sales = daily_orders.groupby(['category', 'item']).agg({
                        'qty': 'sum',
                        'total_sale': 'sum',
                        'profit': 'sum'
                    }).reset_index()
                    st.dataframe(item_sales, use_container_width=True)

# ======================
# BACKUP TAB
# ======================
with tab_backup:
    st.header("💾 Database Backup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Create Backup")
        if st.button("🔒 Create New Backup", use_container_width=True):
            backup_path = create_backup()
            st.success(f"Backup created at: {backup_path}")
    
    with col2:
        st.subheader("Restore Backup")
        available_backups = sorted(
            [d for d in os.listdir(DATA_FOLDER + "backups/") 
            if os.path.isdir(DATA_FOLDER + "backups/" + d)
        )
        
        selected_backup = st.selectbox("Available Backups", available_backups)
        if st.button("🔄 Restore Selected Backup", use_container_width=True):
            if restore_backup(selected_backup):
                st.success("Backup restored successfully! Please restart the app.")
            else:
                st.error("Restoration failed")
    
    st.subheader("Database Status")
    st.json({
        db_name: {
            "size": f"{os.path.getsize(db_path)/1024:.1f} KB" if os.path.exists(db_path) else "Missing",
            "last_modified": datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M') 
            if os.path.exists(db_path) else "Never"
        } 
        for db_name, db_path in DATABASES.items()
    })
