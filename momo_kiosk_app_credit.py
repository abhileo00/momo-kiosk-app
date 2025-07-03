import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import shutil
import os
import zipfile
from passlib.hash import pbkdf2_sha256
from typing import Optional, Tuple, List, Dict
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='food_order_pro.log'
)
logger = logging.getLogger(__name__)

# Constants
DB_FILE = "food_orders.db"
BACKUP_DIR = "backups/"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Database Models
class Database:
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database tables"""
        with self._get_connection() as conn:
            c = conn.cursor()
            
            # Create tables
            c.execute('''CREATE TABLE IF NOT EXISTS orders
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          timestamp TEXT,
                          customer_id INTEGER,
                          items TEXT,
                          total REAL,
                          payment_mode TEXT,
                          status TEXT,
                          staff TEXT,
                          FOREIGN KEY(customer_id) REFERENCES customers(id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS customers
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT,
                          phone TEXT UNIQUE,
                          credit_limit REAL DEFAULT 0,
                          credit_balance REAL DEFAULT 0,
                          total_orders INTEGER DEFAULT 0,
                          total_spent REAL DEFAULT 0,
                          created_at TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS credit_ledger
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          customer_id INTEGER,
                          amount REAL,
                          transaction_type TEXT,
                          description TEXT,
                          timestamp TEXT,
                          FOREIGN KEY(customer_id) REFERENCES customers(id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS menu
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          category TEXT,
                          item TEXT UNIQUE,
                          price REAL,
                          cost REAL,
                          stock INTEGER)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          username TEXT UNIQUE,
                          password TEXT,
                          role TEXT)''')
            
            # Insert default admin if not exists
            c.execute("SELECT 1 FROM users WHERE username='admin'")
            if not c.fetchone():
                hashed_pw = hash_password("admin123")
                c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                         ("admin", hashed_pw, "Admin"))
            
            conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with error handling"""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def execute_query(self, query: str, params: Tuple = (), commit: bool = False) -> Optional[sqlite3.Cursor]:
        """Execute a database query with error handling"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                return cursor
        except sqlite3.Error as e:
            logger.error(f"Query execution error: {e}")
            st.error(f"Database error: {str(e)}")
            return None

# Security Functions
def hash_password(password: str) -> str:
    """Securely hash password using PBKDF2"""
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hashed version"""
    return pbkdf2_sha256.verify(password, hashed)

# Authentication
def authenticate(username: str, password: str) -> Optional[str]:
    """Authenticate user and return role if successful"""
    db = Database()
    result = db.execute_query(
        "SELECT password, role FROM users WHERE username = ?", 
        (username,)
    )
    
    if result:
        user_data = result.fetchone()
        if user_data and verify_password(password, user_data[0]):
            return user_data[1]  # Return role
    return None

# Backup Functions
def create_backup() -> Optional[str]:
    """Create a compressed backup of the database"""
    try:
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = os.path.join(BACKUP_DIR, f"{backup_name}.zip")
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(DB_FILE, arcname=os.path.basename(DB_FILE))
        
        logger.info(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        st.error(f"Backup failed: {str(e)}")
        return None

def restore_backup(backup_file: str) -> bool:
    """Restore database from backup"""
    try:
        # Extract backup
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            zipf.extractall(os.path.dirname(DB_FILE))
        
        logger.info(f"Database restored from {backup_file}")
        return True
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        st.error(f"Restore failed: {str(e)}")
        return False

# Customer Management
def register_customer(name: str, phone: str, credit_limit: float = 0) -> bool:
    """Register a new customer"""
    if not phone.strip():
        st.error("Phone number is required")
        return False
    
    db = Database()
    try:
        db.execute_query(
            """INSERT INTO customers 
               (name, phone, credit_limit, created_at) 
               VALUES (?, ?, ?, ?)""",
            (name.strip(), phone.strip(), credit_limit, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            commit=True
        )
        st.success("Customer registered successfully!")
        return True
    except sqlite3.IntegrityError:
        st.error("Customer with this phone number already exists")
        return False

def update_customer_credit(customer_id: int, amount: float, transaction_type: str, description: str) -> bool:
    """Update customer credit ledger"""
    db = Database()
    
    try:
        # Update credit balance
        if transaction_type == "CREDIT":
            db.execute_query(
                """UPDATE customers 
                   SET credit_balance = credit_balance + ? 
                   WHERE id = ?""",
                (amount, customer_id),
                commit=True
            )
        elif transaction_type == "PAYMENT":
            db.execute_query(
                """UPDATE customers 
                   SET credit_balance = credit_balance - ? 
                   WHERE id = ?""",
                (amount, customer_id),
                commit=True
            )
        
        # Add to ledger
        db.execute_query(
            """INSERT INTO credit_ledger 
               (customer_id, amount, transaction_type, description, timestamp) 
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, amount, transaction_type, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            commit=True
        )
        return True
    except sqlite3.Error as e:
        logger.error(f"Credit update failed: {e}")
        return False

def get_customer_by_phone(phone: str) -> Optional[Dict]:
    """Get customer details by phone number"""
    db = Database()
    result = db.execute_query(
        "SELECT id, name, phone, credit_limit, credit_balance FROM customers WHERE phone = ?",
        (phone,)
    )
    
    if result:
        row = result.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "phone": row[2],
                "credit_limit": row[3],
                "credit_balance": row[4]
            }
    return None

# Order Management
def submit_order(customer_id: Optional[int], items: List[Dict], total: float, payment_mode: str, staff: str) -> bool:
    """Submit a new order"""
    db = Database()
    
    try:
        # Save order
        db.execute_query(
            """INSERT INTO orders 
               (timestamp, customer_id, items, total, payment_mode, status, staff) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
             customer_id if customer_id else None,
             str(items), 
             total, 
             payment_mode, 
             "Completed", 
             staff),
            commit=True
        )
        
        # Update customer stats if registered customer
        if customer_id:
            db.execute_query(
                """UPDATE customers 
                   SET total_orders = total_orders + 1,
                       total_spent = total_spent + ?
                   WHERE id = ?""",
                (total, customer_id),
                commit=True
            )
            
            # If credit payment, update credit balance
            if payment_mode == "Credit":
                update_customer_credit(
                    customer_id,
                    total,
                    "CREDIT",
                    f"Order purchase - ₹{total}"
                )
        
        # Update inventory
        for item in items:
            db.execute_query(
                "UPDATE menu SET stock = stock - ? WHERE item = ?",
                (item['quantity'], item['item']),
                commit=True
            )
        
        return True
    except sqlite3.Error as e:
        logger.error(f"Order submission failed: {e}")
        return False

# UI Components
def login_screen() -> None:
    """Display login screen"""
    st.title("Food Order Pro - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            role = authenticate(username, password)
            if role:
                st.session_state.current_user = username
                st.session_state.user_role = role
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

def order_tab() -> None:
    """Order management tab"""
    st.header("New Order")
    
    # Customer Section
    col1, col2 = st.columns(2)
    with col1:
        customer_phone = st.text_input(
            "Customer Phone (for credit)", 
            placeholder="Enter registered phone number",
            key="customer_phone"
        )
    
    with col2:
        if customer_phone:
            customer = get_customer_by_phone(customer_phone)
            if customer:
                st.markdown(f"""
                    **Customer:** {customer['name']}  
                    **Credit Limit:** ₹{customer['credit_limit']}  
                    **Available Credit:** ₹{customer['credit_limit'] - customer['credit_balance']}
                """)
            else:
                st.warning("Not registered. Credit not available.")
    
    # Menu Selection
    db = Database()
    menu_df = pd.read_sql("SELECT * FROM menu WHERE stock > 0", db._get_connection())
    categories = menu_df['category'].unique()
    
    category = st.selectbox("Select Category", categories)
    items = menu_df[menu_df['category'] == category]
    
    for _, item in items.iterrows():
        with st.expander(f"{item['item']} - ₹{item['price']} (Stock: {item['stock']})"):
            qty = st.number_input(
                "Quantity", 
                min_value=0, 
                max_value=item['stock'],
                key=f"qty_{item['item']}"
            )
            
            if qty > 0 and st.button(f"Add {item['item']}", key=f"add_{item['item']}"):
                order_item = {
                    "item": item['item'],
                    "price": item['price'],
                    "quantity": qty,
                    "total": item['price'] * qty
                }
                if 'current_order' not in st.session_state:
                    st.session_state.current_order = []
                st.session_state.current_order.append(order_item)
                
                st.success(f"Added {qty} × {item['item']}")
                time.sleep(0.5)
                st.rerun()
    
    # Order Summary
    if 'current_order' in st.session_state and st.session_state.current_order:
        st.subheader("Order Summary")
        order_df = pd.DataFrame(st.session_state.current_order)
        st.dataframe(order_df)
        
        total = order_df['total'].sum()
        st.markdown(f"**Total: ₹{total}**")
        
        # Payment options - disable credit if customer not registered
        customer = get_customer_by_phone(customer_phone) if customer_phone else None
        payment_options = ["Cash", "Online"]
        
        if customer:
            available_credit = customer['credit_limit'] - customer['credit_balance']
            if total <= available_credit:
                payment_options.insert(1, "Credit")
            else:
                st.warning(f"Insufficient credit (Available: ₹{available_credit})")
        
        payment_mode = st.radio("Payment Method", payment_options)
        
        if st.button("Submit Order"):
            customer_id = customer['id'] if customer else None
            
            if payment_mode == "Credit" and not customer_id:
                st.error("Credit only available for registered customers")
                return
            
            success = submit_order(
                customer_id,
                st.session_state.current_order,
                total,
                payment_mode,
                st.session_state.current_user
            )
            
            if success:
                st.success("Order submitted successfully!")
                del st.session_state.current_order
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to submit order")

def customers_tab() -> None:
    """Customer management tab"""
    st.header("Customer Management")
    
    tab1, tab2, tab3 = st.tabs(["View Customers", "Register Customer", "Credit Ledger"])
    
    with tab1:
        db = Database()
        customers = pd.read_sql("SELECT * FROM customers", db._get_connection())
        if not customers.empty:
            st.dataframe(customers)
        else:
            st.info("No customers found")
    
    with tab2:
        with st.form("customer_form"):
            name = st.text_input("Full Name*", key="cust_name")
            phone = st.text_input("Phone Number*", key="cust_phone")
            credit_limit = st.number_input("Credit Limit (₹)", min_value=0.0, value=0.0)
            
            if st.form_submit_button("Register Customer"):
                if not name.strip() or not phone.strip():
                    st.error("Name and phone are required fields")
                else:
                    if register_customer(name, phone, credit_limit):
                        st.rerun()
    
    with tab3:
        db = Database()
        customers = pd.read_sql("SELECT id, name, phone FROM customers", db._get_connection())
        
        if not customers.empty:
            selected_customer = st.selectbox(
                "Select Customer",
                customers.apply(lambda x: f"{x['name']} ({x['phone']})", axis=1)
            )
            
            if selected_customer:
                customer_id = int(selected_customer.split("(")[-1].rstrip(")"))
                ledger = pd.read_sql(
                    "SELECT * FROM credit_ledger WHERE customer_id = ? ORDER BY timestamp DESC",
                    db._get_connection(),
                    params=(customer_id,)
                )
                
                if not ledger.empty:
                    st.dataframe(ledger)
                    
                    # Payment form
                    with st.form("payment_form"):
                        amount = st.number_input("Payment Amount", min_value=0.01)
                        description = st.text_input("Description")
                        
                        if st.form_submit_button("Record Payment"):
                            if update_customer_credit(
                                customer_id,
                                amount,
                                "PAYMENT",
                                description or "Payment received"
                            ):
                                st.success("Payment recorded!")
                                st.rerun()
                            else:
                                st.error("Failed to record payment")
                else:
                    st.info("No credit transactions for this customer")
        else:
            st.info("No customers available")

def inventory_tab() -> None:
    """Inventory management tab"""
    st.header("Inventory Management")
    
    db = Database()
    menu_items = pd.read_sql("SELECT * FROM menu", db._get_connection())
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Current Inventory")
        edited_items = st.data_editor(
            menu_items,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", min_value=0),
                "price": st.column_config.NumberColumn("Price", min_value=0.0, format="₹%.2f"),
                "cost": st.column_config.NumberColumn("Cost", min_value=0.0, format="₹%.2f")
            },
            key="inventory_editor"
        )
        
        if st.button("Update Inventory"):
            try:
                edited_items.to_sql('menu', db._get_connection(), if_exists='replace', index=False)
                st.success("Inventory updated!")
                st.rerun()
            except sqlite3.Error as e:
                st.error(f"Failed to update inventory: {str(e)}")
    
    with col2:
        st.subheader("Add New Item")
        with st.form("new_item_form"):
            category = st.selectbox("Category", ["Momos", "Sandwich", "Maggi", "Beverage"])
            item = st.text_input("Item Name*")
            price = st.number_input("Price (₹)*", min_value=0.0)
            cost = st.number_input("Cost (₹)*", min_value=0.0)
            stock = st.number_input("Initial Stock*", min_value=0)
            
            if st.form_submit_button("Add Item"):
                if not item.strip():
                    st.error("Item name is required")
                else:
                    try:
                        db.execute_query(
                            """INSERT INTO menu 
                               (category, item, price, cost, stock) 
                               VALUES (?, ?, ?, ?, ?)""",
                            (category, item.strip(), price, cost, stock),
                            commit=True
                        )
                        st.success("Item added to menu!")
                        st.rerun()
                    except sqlite3.IntegrityError:
            
