       )
            with col2:
                filter_stock = st.selectbox(
                    "Filter by Stock Level",
                    ["All", "Low Stock (< min)", "Out of Stock", "In Stock"],
                    key="stock_filter"
                )
            
            query = "SELECT * FROM menu WHERE item != 'Sample Item'"
            params = []
            
            if filter_category != "All Categories":
                query += " AND category = ?"
                params.append(filter_category)
            
            if filter_stock == "Low Stock (< min)":
                query += " AND stock <= min_stock AND stock > 0"
            elif filter_stock == "Out of Stock":
                query += " AND stock = 0"
            elif filter_stock == "In Stock":
                query += " AND stock > 0"
            
            query += " ORDER BY category, item"
            
            inventory = pd.read_sql(query, conn, params=params if params else None)
            
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import hashlib
import shutil
import os
import ast
import plotly.express as px
from pathlib import Path

# Database Configuration
DB_FILE = "food_hub.db"
BACKUP_DIR = "backups/"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Initialize database with enhanced schema
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables with improved schema
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  customer_id INTEGER,
                  items TEXT,
                  subtotal REAL,
                  tax REAL,
                  discount REAL,
                  total REAL,
                  payment_mode TEXT,
                  status TEXT DEFAULT 'Pending',
                  staff_id INTEGER,
                  notes TEXT,
                  FOREIGN KEY(customer_id) REFERENCES customers(id),
                  FOREIGN KEY(staff_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  phone TEXT UNIQUE,
                  email TEXT,
                  address TEXT,
                  credit_balance REAL DEFAULT 0,
                  total_orders INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0,
                  join_date TEXT,
                  last_order_date TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category TEXT,
                  item TEXT UNIQUE,
                  description TEXT,
                  price REAL,
                  cost REAL,
                  stock INTEGER,
                  min_stock INTEGER DEFAULT 5,
                  is_available INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  full_name TEXT,
                  role TEXT,
                  is_active INTEGER DEFAULT 1,
                  last_login TEXT)''')
    
    # Insert default admin if not exists
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)", 
                 ("admin", hash_password("admin123"), "System Administrator", "Admin"))
    
    # Create indexes for better performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_menu_category ON menu(category)")
    
    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    c = conn.cursor()
    c.execute("SELECT id, password, role FROM users WHERE username = ? AND is_active = 1", (username,))
    result = c.fetchone()
    if result and result[1] == hash_password(password):
        # Update last login
        c.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result[0]))
        conn.commit()
        return result[0], result[2]  # Return user_id and role
    return None, None

# Initialize database
conn = init_db()

# Session state management
def init_session_state():
    defaults = {
        'current_order': [],
        'current_customer': None,
        'current_user_id': None,
        'current_user_role': None,
        'current_user_name': None,
        'edit_item': None,
        'edit_customer': None,
        'edit_user': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Login Screen
if not st.session_state.current_user_id:
    st.title("Food Hub - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            user_id, role = authenticate(username, password)
            if user_id:
                st.session_state.current_user_id = user_id
                st.session_state.current_user_role = role
                # Get user full name
                c = conn.cursor()
                c.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
                result = c.fetchone()
                st.session_state.current_user_name = result[0] if result else username
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# ======================
# CORE FUNCTIONS
# ======================

def create_backup():
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_DIR}foodhub_backup_{timestamp}.db"
    shutil.copy2(DB_FILE, backup_file)
    return backup_file

def get_menu_items(category_filter=None, available_only=True):
    """Retrieve menu items with optional filters"""
    query = "SELECT * FROM menu WHERE item != 'Sample Item'"
    conditions = []
    params = []
    
    if available_only:
        conditions.append("is_available = 1")
    if category_filter:
        conditions.append("category = ?")
        params.append(category_filter)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    return pd.read_sql(query, conn, params=params if params else None)

def process_order(customer_id, items, payment_mode, notes=""):
    """Process and save an order to the database"""
    try:
        subtotal = sum(item['total'] for item in items)
        tax = subtotal * 0.1  # Example 10% tax
        total = subtotal + tax
        
        order_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": customer_id,
            "items": str(items),
            "subtotal": subtotal,
            "tax": tax,
            "discount": 0,  # Could be calculated based on customer loyalty
            "total": total,
            "payment_mode": payment_mode,
            "status": "Completed",
            "staff_id": st.session_state.current_user_id,
            "notes": notes
        }
        
        # Start transaction
        with conn:
            # Insert order
            order_df = pd.DataFrame([order_data])
            order_df.to_sql('orders', conn, if_exists='append', index=False)
            
            # Update inventory
            for item in items:
                conn.execute("UPDATE menu SET stock = stock - ? WHERE item = ?", 
                           (item['quantity'], item['item']))
            
            # Update customer stats if not walk-in
            if customer_id and customer_id > 0:
                conn.execute("""
                    UPDATE customers 
                    SET total_orders = total_orders + 1,
                        total_spent = total_spent + ?,
                        last_order_date = ?
                    WHERE id = ?
                """, (total, order_data['timestamp'], customer_id))
            
            # If credit payment, update balance
            if payment_mode == "Credit" and customer_id:
                conn.execute("""
                    UPDATE customers 
                    SET credit_balance = credit_balance + ?
                    WHERE id = ?
                """, (total, customer_id))
        
        return True
    except Exception as e:
        st.error(f"Error processing order: {str(e)}")
        conn.rollback()
        return False

def order_tab():
    st.header("New Order")
    
    # Customer Selection
    customers = pd.read_sql("SELECT id, name, phone FROM customers WHERE is_active = 1 ORDER BY name", conn)
    customer_options = {0: "Walk-in Customer"}
    customer_options.update({row['id']: f"{row['name']} ({row['phone']})" for _, row in customers.iterrows()})
    
    selected_customer = st.selectbox(
        "Select Customer",
        options=list(customer_options.keys()),
        format_func=lambda x: customer_options[x]
    )
    
    # Add new customer on the fly
    with st.expander("Add New Customer", expanded=False):
        with st.form("quick_customer_form"):
            name = st.text_input("Name*")
            phone = st.text_input("Phone*")
            email = st.text_input("Email")
            if st.form_submit_button("Save Customer"):
                if name and phone:
                    try:
                        conn.execute(
                            "INSERT INTO customers (name, phone, email, join_date) VALUES (?, ?, ?, ?)",
                            (name, phone, email, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit()
                        st.success("Customer added successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Customer with this phone already exists")
                else:
                    st.error("Name and phone are required fields")
    
    # Menu Selection
    menu_df = get_menu_items(available_only=True)
    categories = menu_df['category'].unique()
    
    if not categories:
        st.warning("No menu categories available. Please add categories in Inventory Management.")
        return
    
    category = st.selectbox("Menu Category", categories)
    items = menu_df[menu_df['category'] == category]
    
    if items.empty:
        st.info("No items available in this category")
        return
    
    # Display menu items in columns for better layout
    cols = st.columns(3)
    for idx, item in items.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"**{item['item']}** - ₹{item['price']}")
                if item['description']:
                    st.caption(item['description'])
                stock_status = "In Stock" if item['stock'] > item['min_stock'] else "Low Stock" if item['stock'] > 0 else "Out of Stock"
                st.write(f"{stock_status}: {item['stock']} (min: {item['min_stock']})")
                
                qty = st.number_input(
                    "Quantity",
                    min_value=0,
                    max_value=item['stock'],
                    key=f"qty_{item['id']}",
                    label_visibility="collapsed"
                )
                
                if qty > 0 and st.button("Add to Order", key=f"add_{item['id']}"):
                    order_item = {
                        "item": item['item'],
                        "price": item['price'],
                        "quantity": qty,
                        "total": item['price'] * qty
                    }
                    st.session_state.current_order.append(order_item)
                    st.success(f"Added {qty} × {item['item']}")
                    time.sleep(0.3)
                    st.rerun()
    
    # Order Summary
    if st.session_state.current_order:
        st.subheader("Order Summary")
        order_df = pd.DataFrame(st.session_state.current_order)
        
        # Display order items with remove option
        for i, item in enumerate(st.session_state.current_order):
            cols = st.columns([4, 1, 1, 1])
            cols[0].write(f"{item['quantity']} × {item['item']}")
            cols[1].write(f"₹{item['price']}")
            cols[2].write(f"₹{item['total']}")
            if cols[3].button("Remove", key=f"remove_{i}"):
                st.session_state.current_order.pop(i)
                st.rerun()
        
        subtotal = order_df['total'].sum()
        tax = subtotal * 0.1
        total = subtotal + tax
        
        st.markdown(f"""
        **Subtotal:** ₹{subtotal:.2f}  
        **Tax (10%):** ₹{tax:.2f}  
        **Total:** ₹{total:.2f}
        """)
        
        payment_mode = st.radio("Payment Method", ["Cash", "Credit", "Online", "Card"])
        notes = st.text_area("Order Notes")
        
        if st.button("Submit Order", type="primary"):
            if payment_mode == "Credit" and selected_customer == 0:
                st.error("Credit payment requires selecting a customer")
            else:
                if process_order(selected_customer if selected_customer != 0 else None, 
                               st.session_state.current_order, 
                               payment_mode,
                               notes):
                    st.success("Order submitted successfully!")
                    st.session_state.current_order = []
                    time.sleep(1)
                    st.rerun()

def customers_tab():
    st.header("Customer Management")
    
    tab1, tab2 = st.tabs(["Customer Directory", "Customer Details"])
    
    with tab1:
        st.subheader("All Customers")
        
        # Customer search and filters
        col1, col2 = st.columns(2)
        with col1:
            search_query = st.text_input("Search by name or phone")
        with col2:
            show_inactive = st.checkbox("Show inactive customers")
        
        # Build query
        query = "SELECT * FROM customers"
        conditions = []
        params = []
        
        if search_query:
            conditions.append("(name LIKE ? OR phone LIKE ?)")
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        if not show_inactive:
            conditions.append("is_active = 1")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY name"
        
        customers = pd.read_sql(query, conn, params=params)
        
        if not customers.empty:
            # Display customer table with action buttons
            for _, customer in customers.iterrows():
                with st.expander(f"{customer['name']} - {customer['phone']}"):
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].write(f"**Orders:** {customer['total_orders']}")
                    cols[1].write(f"**Spent:** ₹{customer['total_spent']:.2f}")
                    cols[2].write(f"**Credit:** ₹{customer['credit_balance']:.2f}")
                    if cols[3].button("Edit", key=f"edit_{customer['id']}"):
                        st.session_state.edit_customer = customer['id']
                        st.rerun()
        else:
            st.info("No customers found")
    
    with tab2:
        if st.session_state.edit_customer:
            # Edit existing customer
            customer = pd.read_sql(
                "SELECT * FROM customers WHERE id = ?", 
                conn, 
                params=(st.session_state.edit_customer,)
            ).iloc[0]
            
            st.subheader(f"Editing: {customer['name']}")
        else:
            # Add new customer
            st.subheader("Add New Customer")
            customer = None
        
        with st.form("customer_form"):
            name = st.text_input("Full Name", value=customer['name'] if customer else "")
            phone = st.text_input("Phone Number", value=customer['phone'] if customer else "")
            email = st.text_input("Email", value=customer['email'] if customer else "")
            address = st.text_area("Address", value=customer['address'] if customer else "")
            credit = st.number_input("Credit Balance", 
                                    min_value=0.0, 
                                    value=float(customer['credit_balance']) if customer else 0.0)
            is_active = st.checkbox("Active", value=bool(customer['is_active']) if customer else True
            
            if st.form_submit_button("Save Customer"):
                if not name or not phone:
                    st.error("Name and phone are required")
                else:
                    try:
                        if customer is not None:
                            # Update existing customer
                            conn.execute("""
                                UPDATE customers SET
                                    name = ?,
                                    phone = ?,
                                    email = ?,
                                    address = ?,
                                    credit_balance = ?,
                                    is_active = ?
                                WHERE id = ?
                            """, (name, phone, email, address, credit, int(is_active), customer['id']))
                        else:
                            # Insert new customer
                            conn.execute("""
                                INSERT INTO customers 
                                (name, phone, email, address, credit_balance, join_date, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (name, phone, email, address, credit, datetime.now().strftime("%Y-%m-%d"), int(is_active)))
                        
                        conn.commit()
                        st.session_state.edit_customer = None
                        st.success("Customer saved successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("A customer with this phone number already exists")

def inventory_tab():
    st.header("Inventory Management")
    
    # Get current categories from database
    categories = pd.read_sql("SELECT DISTINCT category FROM menu WHERE item != 'Sample Item'", conn)['category'].tolist()
    
    tab1, tab2 = st.tabs(["Inventory Dashboard", "Category & Item Management"])
    
    with tab1:
        st.subheader("Current Inventory Status")
        
        # Low stock warning
        low_stock = pd.read_sql(
            "SELECT * FROM menu WHERE stock <= min_stock AND item != 'Sample Item' ORDER BY stock ASC", 
            conn
        )
        if not low_stock.empty:
            with st.container(border=True):
                st.warning(f"{len(low_stock)} items below minimum stock level")
                for _, item in low_stock.iterrows():
                    st.write(f"- {item['item']} (Only {item['stock']} left, min: {item['min_stock']})")
        
        # Full inventory display with filtering
        with st.expander("View Full Inventory", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                filter_category = st.selectbox(
                    "Filter by Category",
                    ["All Categories"] + categories,
                    key="inv_filter"
                )
            with col2:
                filter_stock = st.selectbox(
                    "Filter by Stock Level",
                    ["All", "Low Stock (< min)", "Out of Stock", "In Stock"],
                    key="stock_filter"
                )
            
            query = "SELECT * FROM menu WHERE item != 'Sample Item'"
            params = []
            
            if filter_category != "All Categories":
                query += " AND category = ?"
                params.append(filter_category)
            
            if filter_stock == "Low Stock (< min)":
                query += " AND stock <= min_stock AND stock > 0"
            elif filter_stock == "Out of Stock":
                query += " AND stock = 0"
            elif filter_stock == "In Stock":
                query += " AND stock > 0"
            
            query += " ORDER BY category, item"
            
            inventory = pd.read_sql(query, conn, params=params if params else None)
            
            st.dataframe(
                inventory,
                column_config={
                    "category": "Category",
                    "item": "Item Name",
                    "price": st.column_config.NumberColumn("Price (₹)", format="₹%.2f"),
                    "cost": st.column_config.NumberColumn("Cost (₹)", format="₹%.2f"),
                    "stock": st.column_config.NumberColumn("In Stock", min_value=0),
                    "min_stock": st.column_config.NumberColumn("Min Stock", min_value=0),
                    "is_available": st.column_config.CheckboxColumn("Available?")
                },
                hide_index=True,
                use_container_width=True
            )
    
    with tab2:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Manage Categories")
            
            # Add new category
            with st.form("new_category_form", border=True):
                new_category = st.text_input("New Category Name", placeholder="e.g., Breakfast, Desserts")
                if st.form_submit_button("Add Category"):
                    if new_category:
                        # Check if category exists
                        existing = pd.read_sql(
                            "SELECT 1 FROM menu WHERE category = ? LIMIT 1",
                            conn,
                            params=(new_category,)
                        )
                        if not existing.empty:
                            st.error("Category already exists!")
                        else:
                            # Add a sample item to create the category
                            conn.execute(
                                "INSERT INTO menu (category, item, price, stock, is_available) VALUES (?, ?, ?, ?, ?)",
                                (new_category, "Sample Item", 0, 0, 0)
                            )
                            conn.commit()
                            st.success(f"Category '{new_category}' added successfully!")
                            st.rerun()
                    else:
                        st.error("Please enter a category name")
            
            # Current categories list
            st.divider()
            st.write("Existing Categories")
            
            if not categories:
                st.info("No categories found. Add your first category above.")
            else:
                for category in categories:
                    with st.container(border=True):
                        cols = st.columns([4, 1])
                        cols[0].write(f"**{category}**")
                        
                        # Check if category has items before allowing delete
                        has_items = pd.read_sql(
                            "SELECT 1 FROM menu WHERE category = ? AND item != 'Sample Item' LIMIT 1",
                            conn,
                            params=(category,)
                        ).shape[0] > 0
                        
                        if cols[1].button("Delete", key=f"del_{category}", disabled=has_items,
                                         help="Cannot delete categories with items"):
                            conn.execute("DELETE FROM menu WHERE category = ?", (category,))
                            conn.commit()
                            st.success(f"Category '{category}' deleted")
                            st.rerun()
        
        with col2:
            st.subheader("Manage Items")
            
            if st.session_state.edit_item:
                # Edit existing item
                item = pd.read_sql(
                    "SELECT * FROM menu WHERE id = ?", 
                    conn, 
                    params=(st.session_state.edit_item,)
                ).iloc[0]
                
                st.write(f"Editing: {item['item']}")
            else:
                # Add new item
                st.write("Add New Menu Item")
                item = None
            
            with st.form("item_form"):
                # Dynamic category selection
                category = st.selectbox(
                    "Category",
                    categories,
                    index=0 if not item else categories.index(item['category'])
                )
                
                item_name = st.text_input("Item Name", value=item['item'] if item else "")
                description = st.text_area("Description", value=item['description'] if item else "")
                price = st.number_input("Price (₹)", min_value=0.0, step=0.5, value=item['price'] if item else 0.0)
                cost = st.number_input("Cost (₹)", min_value=0.0, step=0.5, value=item['cost'] if item else 0.0)
                stock = st.number_input("Stock", min_value=0, value=item['stock'] if item else 0)
                min_stock = st.number_input("Minimum Stock", min_value=0, value=item['min_stock'] if item else 5)
                
                is_available = st.checkbox("Available", value=bool(item['is_available']) if item else True
                
                if st.form_submit_button("Save Item"):
                    if not item_name or not category:
                        st.error("Item name and category are required")
                    else:
                        try:
                            if item is not None:
                                # Update existing item
                                conn.execute("""
                                    UPDATE menu SET
                                        category = ?,
                                        item = ?,
                                        description = ?,
                                        price = ?,
                                        cost = ?,
                                        stock = ?,
                                        min_stock = ?,
                                        is_available = ?
                                    WHERE id = ?
                                """, (category, item_name, description, price, cost, stock, min_stock, int(is_available), item['id']))
                            else:
                                # Insert new item
                                conn.execute("""
                                    INSERT INTO menu 
                                    (category, item, description, price, cost, stock, min_stock, is_available)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (category, item_name, description, price, cost, stock, min_stock, int(is_available)))
                            
                            conn.commit()
                            st.session_state.edit_item = None
                            st.success("Item saved successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("An item with this name already exists")
            
            # Item actions
            if st.session_state.edit_item:
                if st.button("Cancel Edit"):
                    st.session_state.edit_item = None
                    st.rerun()
                if st.button("Delete Item", type="secondary"):
                    conn.execute("DELETE FROM menu WHERE id = ?", (st.session_state.edit_item,))
                    conn.commit()
                    st.session_state.edit_item = None
                    st.success("Item deleted")
                    st.rerun()

def reports_tab():
    st.header("Sales Analytics")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Convert to strings for SQL query
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Get orders in date range
    orders = pd.read_sql(
        "SELECT * FROM orders WHERE date(timestamp) BETWEEN ? AND ?",
        conn,
        params=(start_str, end_str)
    )
    
    if orders.empty:
        st.info("No orders found in selected date range")
        return
    
    # Convert timestamp and extract date parts
    orders['timestamp'] = pd.to_datetime(orders['timestamp'])
    orders['date'] = orders['timestamp'].dt.date
    orders['day_of_week'] = orders['timestamp'].dt.day_name()
    orders['hour'] = orders['timestamp'].dt.hour
    
    tab1, tab2, tab3, tab4 = st.tabs(["Summary", "Trends", "Products", "Customers"])
    
    with tab1:
        st.subheader("Sales Summary")
        
        # Key metrics
        total_sales = orders['total'].sum()
        avg_order = orders['total'].mean()
        order_count = len(orders)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sales", f"₹{total_sales:,.2f}")
        col2.metric("Average Order", f"₹{avg_order:,.2f}")
        col3.metric("Number of Orders", order_count)
        
        # Payment method breakdown
        st.subheader("Payment Methods")
        payment_counts = orders['payment_mode'].value_counts()
        fig = px.pie(payment_counts, 
                     values=payment_counts.values, 
                     names=payment_counts.index,
                     title="Payment Method Distribution")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Sales Trends")
        
        # Daily sales trend
        daily_sales = orders.groupby('date')['total'].sum().reset_index()
        fig = px.line(daily_sales, x='date', y='total', 
                     title="Daily Sales Trend", 
                     labels={'date': 'Date', 'total': 'Total Sales (₹)'})
        st.plotly_chart(fig, use_container_width=True)
        
        # By day of week
        dow_sales = orders.groupby('day_of_week')['total'].sum().reindex(
            ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        ).reset_index()
        fig = px.bar(dow_sales, x='day_of_week', y='total',
                    title="Sales by Day of Week",
                    labels={'day_of_week': 'Day', 'total': 'Total Sales (₹)'})
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Product Performance")
        
        # Need to parse items JSON (simplified example)
        try:
            items_list = []
            for _, order in orders.iterrows():
                items = ast.literal_eval(order['items'])
                for item in items:
                    items_list.append({
                        'date': order['date'],
                        'item': item['item'],
                        'quantity': item['quantity'],
                        'revenue': item['total']
                    })
            
            if items_list:
                items_df = pd.DataFrame(items_list)
                
                # Top selling items
                top_items = items_df.groupby('item').agg({
                    'quantity': 'sum',
                    'revenue': 'sum'
                }).sort_values('revenue', ascending=False).head(10)
                
                st.write("Top Selling Items")
                st.dataframe(top_items)
                
                # Item trends
                item_trends = items_df.groupby(['date', 'item'])['quantity'].sum().unstack()
                selected_items = st.multiselect(
                    "Select items to compare",
                    options=item_trends.columns,
                    default=list(top_items.index[:3])
                
                if selected_items:
                    fig = px.line(item_trends[selected_items],
                                 title="Item Sales Trends",
                                 labels={'value': 'Quantity Sold', 'date': 'Date'})
                    st.plotly_chart(fig, use_container_width=True)
        except:
            st.warning("Could not parse order items for detailed analysis")
    
    with tab4:
        st.subheader("Customer Insights")
        
        # Top customers
        customer_orders = orders[orders['customer_id'].notnull()]
        if not customer_orders.empty:
            top_customers = customer_orders.groupby('customer_id')['total'].agg(['count', 'sum'])\
                                         .sort_values('sum', ascending=False).head(10)
            
            # Get customer names
            top_customers = top_customers.merge(
                pd.read_sql("SELECT id, name FROM customers", conn),
                left_index=True,
                right_on='id'
            )
            
            st.write("Top Customers by Spending")
            st.dataframe(top_customers.rename(columns={
                'count': 'Orders',
                'sum': 'Total Spent',
                'name': 'Customer'
            }))
        else:
            st.info("No customer orders in selected period")

def admin_tab():
    st.header("Administration")
    
    tab1, tab2, tab3 = st.tabs(["Users", "Backup/Restore", "System Settings"])
    
    with tab1:
        st.subheader("User Management")
        
        users = pd.read_sql("SELECT id, username, full_name, role, last_login FROM users", conn)
        
        # Display users with edit options
        for _, user in users.iterrows():
            with st.expander(f"{user['full_name']} ({user['username']}) - {user['role']}"):
                cols = st.columns([3, 1, 1])
                cols[0].write(f"Last login: {user['last_login'] or 'Never'}")
                
                if cols[1].button("Edit", key=f"edit_user_{user['id']}"):
                    st.session_state.edit_user = user['id']
                    st.rerun()
                
                if user['id'] != st.session_state.current_user_id and cols[2].button("Delete", key=f"del_user_{user['id']}"):
                    conn.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                    conn.commit()
                    st.rerun()
        
        # Add/edit user form
        if 'edit_user' in st.session_state:
            user = pd.read_sql(
                "SELECT * FROM users WHERE id = ?",
                conn,
                params=(st.session_state.edit_user,)
            ).iloc[0]
            
            st.subheader(f"Editing User: {user['username']}")
        else:
            st.subheader("Add New User")
            user = None
        
        with st.form("user_form"):
            username = st.text_input("Username", value=user['username'] if user else "")
            full_name = st.text_input("Full Name", value=user['full_name'] if user else "")
            password = st.text_input("Password", type="password", value="")
            role = st.selectbox(
                "Role",
                ["Admin", "Manager", "Staff"],
                index=0 if not user else ["Admin", "Manager", "Staff"].index(user['role'])
            )
            
            if st.form_submit_button("Save User"):
                if not username or not full_name:
                    st.error("Username and full name are required")
                elif not user and not password:
                    st.error("Password is required for new users")
                else:
                    try:
                        if user is not None:
                            # Update existing user
                            if password:
                                conn.execute("""
                                    UPDATE users SET
                                        username = ?,
                                        full_name = ?,
                                        password = ?,
                                        role = ?
                                    WHERE id = ?
                                """, (username, full_name, hash_password(password), role, user['id']))
                            else:
                                conn.execute("""
                                    UPDATE users SET
                                        username = ?,
                                        full_name = ?,
                                        role = ?
                                    WHERE id = ?
                                """, (username, full_name, role, user['id']))
                        else:
                            # Insert new user
                            conn.execute("""
                                INSERT INTO users 
                                (username, full_name, password, role)
                                VALUES (?, ?, ?, ?)
                            """, (username, full_name, hash_password(password), role))
                        
                        conn.commit()
                        if 'edit_user' in st.session_state:
                            del st.session_state.edit_user
                        st.success("User saved successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Username already exists")
    
    with tab2:
        st.subheader("Backup & Restore")
        
        if st.button("Create Backup Now"):
            backup_file = create_backup()
            st.success(f"Backup created: {backup_file}")
            st.rerun()
        
        st.subheader("Available Backups")
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')], reverse=True)
        
        if backups:
            selected = st.selectbox("Select backup to restore", backups)
            
            if st.button(f"Restore {selected}", type="primary"):
                # Close existing connection
                conn.close()
                # Restore backup
                shutil.copy2(f"{BACKUP_DIR}{selected}", DB_FILE)
                st.success("Database restored! Please refresh the page.")
                time.sleep(2)
                st.rerun()
            
            if st.button(f"Delete {selected}"):
                os.remove(f"{BACKUP_DIR}{selected}")
                st.success("Backup deleted!")
                st.rerun()
        else:
            st.info("No backups available")
    
    with tab3:
        st.subheader("System Configuration")
        st.warning("System settings not implemented in this demo")


# ======================
# MAIN APP LAYOUT
# ======================

st.title("Food Hub Restaurant Management")
st.markdown(f"Welcome, **{st.session_state.current_user_name}** ({st.session_state.current_user_role})")

# Role-based navigation
if st.session_state.current_user_role == "Admin":
    tabs = st.tabs(["Orders", "Customers", "Inventory", "Reports", "Administration"])
    with tabs[0]:
        order_tab()
    with tabs[1]:
        customers_tab()
    with tabs[2]:
        inventory_tab()
    with tabs[3]:
        reports_tab()
    with tabs[4]:
        admin_tab()
elif st.session_state.current_user_role == "Manager":
    tabs = st.tabs(["Orders", "Customers", "Inventory", "Reports"])
    with tabs[0]:
        order_tab()
    with tabs[1]:
        customers_tab()
    with tabs[2]:
        inventory_tab()
    with tabs[3]:
        reports_tab()
else:  # Staff
    tabs = st.tabs(["Orders", "Customers"])
    with tabs[0]:
        order_tab()
    with tabs[1]:
        customers_tab()

# Logout button
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Display current orders in sidebar
if st.session_state.current_order:
    st.sidebar.subheader("Current Order")
    for item in st.session_state.current_order:
        st.sidebar.write(f"{item['quantity']} × {item['item']} - ₹{item['total']}")
    total = sum(item['total'] for item in st.session_state.current_order)
    st.sidebar.markdown(f"**Total:** ₹{total:.2f}")
    if st.sidebar.button("Clear Order"):
        st.session_state.current_order = []
        st.rerun()
