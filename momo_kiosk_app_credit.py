momo_kiosk_pro.py

import streamlit as st import pandas as pd from datetime import datetime, date import os import shutil

======================

DATA CONFIGURATION

======================

DATA_FOLDER = "momo_kiosk_data/" DATABASES = { "orders": DATA_FOLDER + "orders.csv", "menu": DATA_FOLDER + "menu.csv", "customers": DATA_FOLDER + "customers.csv", "credit": DATA_FOLDER + "credit_transactions.csv", "inventory": DATA_FOLDER + "inventory.csv" }

TOPPINGS = { "Extra Cheese": 20, "Masala": 10, "Butter": 10, "Egg": 15 }

======================

DATA MANAGEMENT

======================

def init_data_system(): if not os.path.exists(DATA_FOLDER): os.makedirs(DATA_FOLDER) os.makedirs(DATA_FOLDER + "backups/")

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
        },
        "Drinks": {
            "Tea Small": {"price": 10, "cost": 3},
            "Tea Medium": {"price": 15, "cost": 5},
            "Tea Large": {"price": 20, "cost": 7},
            "Coffee": {"price": 20, "cost": 7}
        }
    }
    save_menu_data(default_menu)

def load_db(db_name): try: return pd.read_csv(DATABASES[db_name]) except: return pd.DataFrame()

def save_db(db_name, df): df.to_csv(DATABASES[db_name], index=False)

def load_menu(): menu = {} df = load_db("menu") if not df.empty: for category in df['category'].unique(): category_items = {} for _, row in df[df['category'] == category].iterrows(): category_items[row['item']] = { "price": row['price'], "cost": row['cost'] } menu[category] = category_items return menu

def save_menu_data(menu): rows = [] for category, items in menu.items(): for item, details in items.items(): rows.append({ "category": category, "item": item, "price": details["price"], "cost": details["cost"] }) save_db("menu", pd.DataFrame(rows))

def create_backup(): backup_dir = f"{DATA_FOLDER}backups/{datetime.now().strftime('%Y-%m-%d_%H-%M')}/" os.makedirs(backup_dir, exist_ok=True) for db_name, db_path in DATABASES.items(): if os.path.exists(db_path): shutil.copy2(db_path, backup_dir + db_name + ".csv") return backup_dir

def restore_backup(backup_date): backup_dir = f"{DATA_FOLDER}backups/{backup_date}/" if os.path.exists(backup_dir): for db_name in DATABASES.keys(): backup_path = backup_dir + db_name + ".csv" if os.path.exists(backup_path): shutil.copy2(backup_path, DATABASES[db_name]) return True return False

======================

STREAMLIT APP START

======================

st.set_page_config(page_title="Momo Kiosk Pro", layout="wide") init_data_system()

if "user_role" not in st.session_state: st.session_state.user_role = None if "orders" not in st.session_state: st.session_state.orders = [] if "order_counter" not in st.session_state: st.session_state.order_counter = 1 if "menu" not in st.session_state: st.session_state.menu = load_menu()

with st.sidebar: st.title("🔐 Login") st.session_state.user_role = st.selectbox("Login as", ["Admin", "Staff"])

Tabs logic based on role

order_tab = st.tabs(["📝 Order"])[0] if st.session_state.user_role == "Admin": tab_inventory, tab_customers, tab_reports, tab_backup = st.tabs([ "📦 Inventory", "👥 Customers", "📊 Reports", "💾 Backup"])

... (Remaining logic from your provided script including order tab, etc.)

Will continue in next part if needed

