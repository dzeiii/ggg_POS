from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime
import math
from contextlib import contextmanager
import pandas as pd
import streamlit as st
from data_structures import LinkedListCart, AVLTree, MinHeap, HeapEntry

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "pos.db"

st.set_page_config(page_title="Gulps and Grubs at the Garage", page_icon="🍹🍟", layout="wide")

# ----------------------------- Database layer -----------------------------
def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_session():
    """Commit on success, roll back on error, and always close the connection."""
    conn = connect_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            category TEXT NOT NULL DEFAULT 'General',
            price REAL NOT NULL CHECK(price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL NOT NULL CHECK(total >= 0),
            transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Sale','Pickup')),
            customer_name TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL REFERENCES transactions(id),
            product_id INTEGER,
            product_name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            subtotal REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pickup_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
            customer_name TEXT NOT NULL,
            priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Completed','Cancelled')),
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_products_active_name ON products(active, name);
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_pickup_status_priority ON pickup_orders(status, priority, created_at);
        """)


def query_all(sql, params=()):
    with db_session() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql, params=()):
    with db_session() as conn:
        return conn.execute(sql, params).fetchone()


def load_product_tree(include_inactive=False):
    tree = AVLTree()
    sql = "SELECT * FROM products" + ("" if include_inactive else " WHERE active=1")
    for row in query_all(sql):
        product = dict(row)
        tree.insert(product["name"], product)
    return tree


def load_pending_heap():
    heap = MinHeap()
    rows = query_all("""SELECT po.id, po.priority, po.created_at, po.customer_name,
                       t.total, po.status
                       FROM pickup_orders po JOIN transactions t ON t.id=po.transaction_id
                       WHERE po.status='Pending'""")
    for row in rows:
        heap.push(HeapEntry(int(row["priority"]), int(row["id"]), row["created_at"],
                            row["customer_name"], float(row["total"]), row["status"]))
    return heap


def validate_product(name, category, price, stock):
    name = name.strip()
    category = category.strip() or "General"
    if not name or len(name) > 100:
        raise ValueError("Product name must contain 1–100 characters.")
    if len(category) > 60:
        raise ValueError("Category must contain no more than 60 characters.")
    if not math.isfinite(float(price)) or float(price) < 0 or float(price) > 1_000_000:
        raise ValueError("Price must be a valid amount from ₱0 to ₱1,000,000.")
    if isinstance(stock, bool) or int(stock) != stock or int(stock) < 0 or int(stock) > 1_000_000:
        raise ValueError("Stock must be a whole number from 0 to 1,000,000.")
    return name, category, round(float(price), 2), int(stock)


def money(value):
    return f"₱{float(value):,.2f}"


def format_time(value):
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %I:%M %p")
    except (TypeError, ValueError):
        return value or "—"


def ensure_cart():
    if "cart" not in st.session_state:
        st.session_state.cart = LinkedListCart()


def add_product_to_cart(product, quantity):
    ensure_cart()
    if quantity <= 0:
        raise ValueError("Quantity must be at least 1.")
    if quantity > int(product["stock"]):
        raise ValueError(f"Only {product['stock']} unit(s) of {product['name']} are in stock.")
    existing = next((x for x in st.session_state.cart.items() if x["product_id"] == product["id"]), None)
    total_qty = quantity + (existing["quantity"] if existing else 0)
    if total_qty > int(product["stock"]):
        raise ValueError(f"Cart quantity for {product['name']} cannot exceed current stock ({product['stock']}).")
    st.session_state.cart.add(product["id"], product["name"], float(product["price"]), int(quantity))


def checkout_cart(transaction_type, customer_name="", priority=3):
    ensure_cart()
    items = st.session_state.cart.items()
    if not items:
        raise ValueError("The shopping cart is empty.")
    if transaction_type == "Pickup" and not customer_name.strip():
        raise ValueError("Enter the customer's name for a pickup order.")
    total = round(sum(float(item["price"]) * int(item["quantity"]) for item in items), 2)
    now = datetime.now().isoformat(timespec="seconds")
    # One transaction protects the sale, stock changes, item records, and optional pickup ticket.
    with db_session() as conn:
        for item in items:
            row = conn.execute("SELECT name, price, stock, active FROM products WHERE id=?", (item["product_id"],)).fetchone()
            if row is None or not row["active"]:
                raise ValueError(f"Product '{item['name']}' is no longer available. Refresh the cart.")
            if int(row["stock"]) < int(item["quantity"]):
                raise ValueError(f"Insufficient stock for {row['name']}. Available: {row['stock']}.")
        cursor = conn.execute("INSERT INTO transactions(total, transaction_type, customer_name, created_at) VALUES(?,?,?,?)",
                              (total, transaction_type, customer_name.strip() or None, now))
        transaction_id = int(cursor.lastrowid)
        for item in items:
            conn.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                         (item["quantity"], item["product_id"], item["quantity"]))
            conn.execute("INSERT INTO transaction_items(transaction_id, product_id, product_name, unit_price, quantity, subtotal) VALUES(?,?,?,?,?,?)",
                         (transaction_id, item["product_id"], item["name"], item["price"], item["quantity"], item["subtotal"]))
        if transaction_type == "Pickup":
            if int(priority) not in range(1, 6):
                raise ValueError("Priority must be from 1 to 5.")
            conn.execute("INSERT INTO pickup_orders(transaction_id, customer_name, priority, status, created_at) VALUES(?,?,?,'Pending',?)",
                         (transaction_id, customer_name.strip(), int(priority), now))
    st.session_state.cart.clear()
    return transaction_id, total


init_db()
ensure_cart()

# ----------------------------- Sidebar / navigation -----------------------------
st.sidebar.title("GULPS AND GRUBS")
st.sidebar.caption("Inventory · Sales · Pickup queue")
page = st.sidebar.radio("Navigation", ["Dashboard", "Products", "Checkout", "Pickup Orders", "Transaction History"])
st.sidebar.divider()
st.sidebar.caption("Data is stored locally in pos.db")

st.title("GULPS AND GRUBS POS")
st.caption("Python · Streamlit · SQLite · Manually implemented Linked List, AVL Tree, and Min-Heap")

# ----------------------------- Dashboard -----------------------------
if page == "Dashboard":
    products = query_all("SELECT * FROM products WHERE active=1 ORDER BY name COLLATE NOCASE")
    sales = query_one("SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total FROM transactions WHERE transaction_type='Sale'")
    pickups = query_one("SELECT COUNT(*) AS n FROM pickup_orders WHERE status='Pending'")
    low_stock = query_one("SELECT COUNT(*) AS n FROM products WHERE active=1 AND stock<=5")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active products", len(products))
    c2.metric("Recorded sales", int(sales["n"]))
    c3.metric("Sales revenue", money(sales["total"]))
    c4.metric("Pending pickups", int(pickups["n"]))
    st.subheader("Inventory overview")
    if products:
        df = pd.DataFrame([dict(r) for r in products])
        df = df[["id", "name", "category", "price", "stock"]].rename(columns={"id":"ID", "name":"Product", "category":"Category", "price":"Price (₱)", "stock":"Stock"})
        st.dataframe(df, use_container_width=True, hide_index=True)
        low = [dict(r) for r in products if int(r["stock"]) <= 5]
        if low:
            st.warning("Low stock (5 or fewer): " + ", ".join(f"{p['name']} ({p['stock']})" for p in low))
    else:
        st.info("No products yet. Open Products to add your first items.")
    st.subheader("Data structure status")
    tree = load_product_tree()
    heap = load_pending_heap()
    a, b, c = st.columns(3)
    a.metric("AVL Tree nodes", len(tree.inorder()))
    b.metric("Pending Min-Heap entries", len(heap))
    c.metric("Linked List cart items", len(st.session_state.cart))
    st.caption("AVL Tree search is O(log n) on average/worst-case due to balancing. Min-Heap insertion/removal is O(log n). Linked List lookup/removal is O(n).")

# ----------------------------- Product management -----------------------------
elif page == "Products":
    st.subheader("Add a product")
    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Product name", max_chars=100)
        category = col2.text_input("Category", value="General", max_chars=60)
        col3, col4 = st.columns(2)
        price = col3.number_input("Price (₱)", min_value=0.0, max_value=1_000_000.0, value=10.0, step=1.0, format="%.2f")
        stock = col4.number_input("Initial stock", min_value=0, max_value=1_000_000, value=0, step=1)
        submitted = st.form_submit_button("Add product", type="primary")
        if submitted:
            try:
                name, category, price, stock = validate_product(name, category, price, stock)
                with db_session() as conn:
                    conn.execute("INSERT INTO products(name, category, price, stock, active, created_at) VALUES(?,?,?,?,1,?)",
                                 (name, category, price, stock, datetime.now().isoformat(timespec="seconds")))
                st.success(f"Added {name}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.IntegrityError:
                st.error("A product with that name already exists. Product names must be unique.")
            except sqlite3.Error as exc:
                st.error(f"Database error: {exc}")

    st.divider()
    st.subheader("Search and manage products")
    search_text = st.text_input("Search by exact name or browse all", placeholder="e.g., Iced Coffee")
    tree = load_product_tree()
    if search_text.strip():
        exact = tree.search(search_text)
        # Prefix/partial matching is a user-friendly browse feature; exact lookup is through the AVL Tree.
        matched = [exact] if exact else [p for p in tree.inorder() if search_text.casefold() in p["name"].casefold()]
    else:
        matched = tree.inorder()
    if matched:
        st.dataframe(pd.DataFrame([{"ID":p["id"], "Product":p["name"], "Category":p["category"], "Price (₱)":p["price"], "Stock":p["stock"]} for p in matched]), use_container_width=True, hide_index=True)
        ids = {f"{p['name']} (ID {p['id']})": p for p in matched}
        selected_label = st.selectbox("Choose a product to edit or deactivate", list(ids.keys()))
        selected = ids[selected_label]
        with st.form("edit_product_form"):
            ec1, ec2 = st.columns(2)
            ename = ec1.text_input("Name", value=selected["name"], max_chars=100)
            ecategory = ec2.text_input("Category", value=selected["category"], max_chars=60)
            ec3, ec4 = st.columns(2)
            eprice = ec3.number_input("Price (₱)", min_value=0.0, max_value=1_000_000.0, value=float(selected["price"]), step=1.0, format="%.2f")
            estock = ec4.number_input("Stock", min_value=0, max_value=1_000_000, value=int(selected["stock"]), step=1)
            save = st.form_submit_button("Save changes")
            if save:
                try:
                    ename, ecategory, eprice, estock = validate_product(ename, ecategory, eprice, estock)
                    with db_session() as conn:
                        conn.execute("UPDATE products SET name=?, category=?, price=?, stock=? WHERE id=? AND active=1",
                                     (ename, ecategory, eprice, estock, selected["id"]))
                    st.success("Product updated.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except sqlite3.IntegrityError:
                    st.error("Another product already uses that name.")
                except sqlite3.Error as exc:
                    st.error(f"Database error: {exc}")
        if st.button("Deactivate selected product", type="secondary"):
            try:
                with db_session() as conn:
                    conn.execute("UPDATE products SET active=0 WHERE id=?", (selected["id"],))
                st.success("Product deactivated. Past transaction records are retained.")
                st.rerun()
            except sqlite3.Error as exc:
                st.error(f"Database error: {exc}")
    else:
        st.info("No matching products found.")
    st.caption("Products are deactivated instead of physically deleted so historical sales records remain intact.")

# ----------------------------- Checkout -----------------------------
elif page == "Checkout":
    st.subheader("Build shopping cart")
    products = [dict(r) for r in query_all("SELECT * FROM products WHERE active=1 AND stock>0 ORDER BY name COLLATE NOCASE")]
    if not products:
        st.info("No in-stock products are available. Add products or restock inventory first.")
    else:
        by_label = {f"{p['name']} — {money(p['price'])} (stock: {p['stock']})":p for p in products}
        with st.form("cart_add_form", clear_on_submit=False):
            label = st.selectbox("Product", list(by_label.keys()))
            quantity = st.number_input("Quantity", min_value=1, max_value=1_000_000, value=1, step=1)
            add = st.form_submit_button("Add to cart")
            if add:
                try:
                    add_product_to_cart(by_label[label], int(quantity))
                    st.success("Item added to cart.")
                except ValueError as exc:
                    st.error(str(exc))
    st.subheader("Current cart (Linked List)")
    cart_items = st.session_state.cart.items()
    if cart_items:
        st.dataframe(pd.DataFrame([{"Product":x["name"], "Unit price":money(x["price"]), "Quantity":x["quantity"], "Subtotal":money(x["subtotal"])} for x in cart_items]), use_container_width=True, hide_index=True)
        labels = {f"{x['name']} (qty {x['quantity']})":x for x in cart_items}
        chosen = st.selectbox("Choose cart item to update/remove", list(labels.keys()))
        item = labels[chosen]
        uq1, uq2 = st.columns([2,1])
        with uq1:
            new_qty = st.number_input("New quantity (0 removes item)", min_value=0, max_value=1_000_000, value=int(item["quantity"]), step=1, key=f"qty_{item['product_id']}")
        with uq2:
            if st.button("Update cart item"):
                try:
                    prod = query_one("SELECT stock FROM products WHERE id=? AND active=1", (item["product_id"],))
                    if new_qty > 0 and (prod is None or new_qty > int(prod["stock"])):
                        raise ValueError(f"Quantity exceeds current available stock ({prod['stock'] if prod else 0}).")
                    st.session_state.cart.set_quantity(item["product_id"], int(new_qty))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.metric("Cart total", money(st.session_state.cart.total()))
        st.divider()
        st.subheader("Complete transaction")
        mode = st.radio("Transaction type", ["Sale", "Pickup"], horizontal=True, help="Pickup orders are placed in the priority queue after the sale is recorded.")
        customer = ""
        priority = 3
        if mode == "Pickup":
            customer = st.text_input("Customer name", max_chars=100)
            priority_label = st.select_slider("Pickup urgency", options=[1,2,3,4,5], value=3, format_func=lambda x: {1:"1 — Highest",2:"2 — High",3:"3 — Normal",4:"4 — Low",5:"5 — Lowest"}[x])
            priority = int(priority_label)
            st.caption("Lower number = more urgent. Equal priorities are processed in creation-time order.")
        if st.button("Complete sale" if mode == "Sale" else "Place pickup order", type="primary", use_container_width=True):
            try:
                transaction_id, total = checkout_cart(mode, customer, priority)
                st.success(f"Transaction #{transaction_id} recorded. Total: {money(total)}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.Error as exc:
                st.error(f"Transaction was not completed because of a database error: {exc}")
        if st.button("Clear entire cart"):
            st.session_state.cart.clear()
            st.rerun()
    else:
        st.info("Your cart is empty. Add a product above to begin.")

# ----------------------------- Pickup queue -----------------------------
elif page == "Pickup Orders":
    st.subheader("Priority-based pickup order queue")
    heap = load_pending_heap()
    top = heap.peek()
    if top:
        st.info(f"Next order: #{top.order_id} · {top.customer_name} · Priority {top.priority} · {money(top.total)}")
        st.caption("The Min-Heap determines the next order by priority (1 is highest), then creation time, then order ID.")
        if st.button("Process next highest-priority order", type="primary"):
            try:
                # Reload immediately before processing to avoid acting on a stale UI snapshot.
                current_heap = load_pending_heap()
                next_order = current_heap.pop()
                if next_order is None:
                    st.warning("There are no pending pickup orders.")
                else:
                    with db_session() as conn:
                        result = conn.execute("UPDATE pickup_orders SET status='Completed', completed_at=? WHERE id=? AND status='Pending'",
                                              (datetime.now().isoformat(timespec="seconds"), next_order.order_id))
                        if result.rowcount != 1:
                            raise ValueError("This order was already processed. Refresh and try again.")
                    st.success(f"Pickup order #{next_order.order_id} marked completed.")
                    st.rerun()
            except (sqlite3.Error, ValueError) as exc:
                st.error(f"Could not process order: {exc}")
    else:
        st.success("No pending pickup orders. Queue is clear.")
    pending = query_all("""SELECT po.id AS order_id, po.customer_name, po.priority, po.status, po.created_at, t.total
                           FROM pickup_orders po JOIN transactions t ON t.id=po.transaction_id
                           WHERE po.status='Pending' ORDER BY po.priority ASC, po.created_at ASC, po.id ASC""")
    if pending:
        st.subheader("Pending orders — heap priority order")
        st.dataframe(pd.DataFrame([{"Order #":r["order_id"], "Customer":r["customer_name"], "Priority":r["priority"], "Total":money(r["total"]), "Created":format_time(r["created_at"])} for r in pending]), use_container_width=True, hide_index=True)
    history = query_all("""SELECT po.id AS order_id, po.customer_name, po.priority, po.status, po.created_at, po.completed_at, t.total
                          FROM pickup_orders po JOIN transactions t ON t.id=po.transaction_id
                          WHERE po.status!='Pending' ORDER BY po.id DESC LIMIT 100""")
    if history:
        st.subheader("Completed pickup orders")
        st.dataframe(pd.DataFrame([{"Order #":r["order_id"], "Customer":r["customer_name"], "Priority":r["priority"], "Total":money(r["total"]), "Status":r["status"], "Created":format_time(r["created_at"]), "Completed":format_time(r["completed_at"])} for r in history]), use_container_width=True, hide_index=True)

# ----------------------------- Transaction history -----------------------------
elif page == "Transaction History":
    st.subheader("Sales and transaction history")
    transactions = query_all("SELECT * FROM transactions ORDER BY id DESC LIMIT 500")
    if transactions:
        st.dataframe(pd.DataFrame([{"Transaction #":r["id"], "Type":r["transaction_type"], "Customer":r["customer_name"] or "—", "Total":money(r["total"]), "Date":format_time(r["created_at"])} for r in transactions]), use_container_width=True, hide_index=True)
        options = {f"#{r['id']} · {r['transaction_type']} · {money(r['total'])} · {format_time(r['created_at'])}":int(r["id"]) for r in transactions}
        selected_tx = st.selectbox("View transaction details", list(options.keys()))
        details = query_all("SELECT product_name, unit_price, quantity, subtotal FROM transaction_items WHERE transaction_id=? ORDER BY id", (options[selected_tx],))
        if details:
            st.dataframe(pd.DataFrame([{"Product":r["product_name"], "Unit price":money(r["unit_price"]), "Quantity":r["quantity"], "Subtotal":money(r["subtotal"])} for r in details]), use_container_width=True, hide_index=True)
        st.download_button("Download transaction history as CSV", data=pd.DataFrame([dict(r) for r in transactions]).to_csv(index=False).encode("utf-8"), file_name="pos_transaction_history.csv", mime="text/csv")
    else:
        st.info("No transactions have been recorded yet.")

st.sidebar.divider()
st.sidebar.caption("Educational prototype. Back up pos.db regularly. This local app does not include user accounts, tax rules, payment gateway integration, or remote multi-user synchronization.")
