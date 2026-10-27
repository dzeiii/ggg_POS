"""
Gulps & Grubs at the Garage - Point-of-Sale System
Data structures (hand-written): Linked List (cart), AVL Tree (products), Min-Heap (order queue)
Storage: SQLite.   Modes: Cashier, Kitchen, Admin (PIN 1234).   Drinks support Small/Medium/Large.
Run:  python gulps_grubs_pos.py
"""
import sqlite3
import random
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

ORANGE, BROWN, CREAM, YELLOW, BUBBLE = "#F08A24", "#4A0F0F", "#FFF0DC", "#FFC72C", "#F7C59A"
FONT = "Trebuchet MS"
ADMIN_PIN = "1234"
PRIORITY = {1: "1 - Rush", 2: "2 - Normal", 3: "3 - Low"}


# ======================= DATA STRUCTURES =======================
# ---- AVL Tree (products keyed by lowercase name) ----
class AVLNode:
    def __init__(s, k, v):
        s.k, s.v, s.l, s.r, s.h = k, v, None, None, 1


def _h(n): return n.h if n else 0
def _upd(n): n.h = 1 + max(_h(n.l), _h(n.r))
def _bal(n): return _h(n.l) - _h(n.r)


def _rot_r(y):
    x = y.l; y.l = x.r; x.r = y; _upd(y); _upd(x); return x


def _rot_l(x):
    y = x.r; x.r = y.l; y.l = x; _upd(x); _upd(y); return y


def _rebalance(n):
    _upd(n); b = _bal(n)
    if b > 1:
        if _bal(n.l) < 0: n.l = _rot_l(n.l)
        return _rot_r(n)
    if b < -1:
        if _bal(n.r) > 0: n.r = _rot_r(n.r)
        return _rot_l(n)
    return n


class AVLTree:
    def __init__(s): s.root = None

    def insert(s, k, v): s.root = s._ins(s.root, k, v)

    def _ins(s, n, k, v):
        if not n: return AVLNode(k, v)
        if k < n.k: n.l = s._ins(n.l, k, v)
        elif k > n.k: n.r = s._ins(n.r, k, v)
        else: n.v = v; return n
        return _rebalance(n)

    def delete(s, k): s.root = s._del(s.root, k)

    def _del(s, n, k):
        if not n: return None
        if k < n.k: n.l = s._del(n.l, k)
        elif k > n.k: n.r = s._del(n.r, k)
        else:
            if not n.l: return n.r
            if not n.r: return n.l
            m = n.r
            while m.l: m = m.l
            n.k, n.v = m.k, m.v
            n.r = s._del(n.r, m.k)
        return _rebalance(n)

    def search(s, k):
        n = s.root
        while n:
            if k == n.k: return n.v
            n = n.l if k < n.k else n.r
        return None

    def inorder(s):
        out = []
        def go(n):
            if n: go(n.l); out.append(n.v); go(n.r)
        go(s.root); return out

    def prefix(s, p):  # all products whose name starts with p, in sorted order
        out = []
        def go(n):
            if not n: return
            if p <= n.k: go(n.l)
            if n.k.startswith(p): out.append(n.v)
            if n.k[:len(p)] <= p: go(n.r)
        go(s.root); return out

    def height(s): return _h(s.root)


# ---- Singly Linked List (shopping cart) ----
class CartNode:
    def __init__(s, item): s.item, s.next = item, None


class CartList:
    def __init__(s): s.head = None; s.size = 0

    def add(s, item):  # merge with same product+size, else append at tail
        cur, last = s.head, None
        while cur:
            if cur.item["pid"] == item["pid"] and cur.item["size"] == item["size"]:
                cur.item["qty"] += item["qty"]; return
            last, cur = cur, cur.next
        node = CartNode(dict(item))
        if last: last.next = node
        else: s.head = node
        s.size += 1

    def remove(s, pid, size):
        cur, prev = s.head, None
        while cur:
            if cur.item["pid"] == pid and cur.item["size"] == size:
                if prev: prev.next = cur.next
                else: s.head = cur.next
                s.size -= 1; return True
            prev, cur = cur, cur.next
        return False

    def clear(s): s.head = None; s.size = 0

    def __iter__(s):
        cur = s.head
        while cur: yield cur.item; cur = cur.next

    def qty_of(s, pid): return sum(i["qty"] for i in s if i["pid"] == pid)
    def total(s): return sum(i["qty"] * i["price"] for i in s)


# ---- Min-Heap (pending orders: lower priority number = more urgent; ties by order id) ----
class MinHeap:
    def __init__(s): s.a = []

    def __len__(s): return len(s.a)

    def push(s, x):
        s.a.append(x); i = len(s.a) - 1
        while i > 0 and s.a[(i - 1) // 2] > s.a[i]:
            p = (i - 1) // 2; s.a[i], s.a[p] = s.a[p], s.a[i]; i = p

    def peek(s): return s.a[0] if s.a else None

    def pop(s):
        if not s.a: return None
        top, last = s.a[0], s.a.pop()
        if s.a:
            s.a[0] = last; i, n = 0, len(s.a)
            while True:
                l, r, m = 2 * i + 1, 2 * i + 2, i
                if l < n and s.a[l] < s.a[m]: m = l
                if r < n and s.a[r] < s.a[m]: m = r
                if m == i: break
                s.a[i], s.a[m] = s.a[m], s.a[i]; i = m
        return top

    def sorted_items(s): return sorted(s.a)


# ======================= DATABASE =======================
class Database:
    def __init__(s, path="gulps_grubs.db"):
        s.c = sqlite3.connect(path)
        s.c.row_factory = sqlite3.Row
        with s.c:
            s.c.executescript("""
            CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL, has_sizes INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sizes(name TEXT PRIMARY KEY, extra REAL NOT NULL, sort INTEGER);
            CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, created TEXT, customer TEXT,
                priority INTEGER, total REAL, status TEXT DEFAULT 'pending');
            CREATE TABLE IF NOT EXISTS order_items(order_id INTEGER, name TEXT, size TEXT, qty INTEGER, unit_price REAL);
            """)
            if not s.c.execute("SELECT 1 FROM products").fetchone():
                s.c.executemany("INSERT INTO products(name,category,price,stock,has_sizes) VALUES(?,?,?,?,?)", [
                    ("Iced Coffee", "Drink", 80, 50, 1), ("Milk Tea", "Drink", 90, 50, 1),
                    ("Lemonade", "Drink", 70, 40, 1), ("Root Beer Float", "Drink", 110, 30, 1),
                    ("Garage Burger", "Food", 150, 30, 0), ("Fries", "Food", 70, 60, 0),
                    ("Nachos", "Food", 120, 25, 0), ("Chicken Wings", "Food", 180, 20, 0)])
                s.c.executemany("INSERT INTO sizes VALUES(?,?,?)", [("Small", 0, 1), ("Medium", 15, 2), ("Large", 30, 3)])

    def products(s): return [dict(r) for r in s.c.execute("SELECT * FROM products")]
    def sizes(s): return [dict(r) for r in s.c.execute("SELECT * FROM sizes ORDER BY sort")]

    def save_sizes(s, d):
        with s.c:
            for n, e in d.items(): s.c.execute("UPDATE sizes SET extra=? WHERE name=?", (e, n))

    def add_product(s, n, c, p, st, hs):
        with s.c: s.c.execute("INSERT INTO products(name,category,price,stock,has_sizes) VALUES(?,?,?,?,?)", (n, c, p, st, hs))

    def update_product(s, pid, n, c, p, st, hs):
        with s.c: s.c.execute("UPDATE products SET name=?,category=?,price=?,stock=?,has_sizes=? WHERE id=?", (n, c, p, st, hs, pid))

    def delete_product(s, pid):
        with s.c: s.c.execute("DELETE FROM products WHERE id=?", (pid,))

    def checkout(s, items, priority, customer):
        need = {}
        for i in items: need[i["pid"]] = need.get(i["pid"], 0) + i["qty"]
        with s.c:
            for pid, q in need.items():
                row = s.c.execute("SELECT name,stock FROM products WHERE id=?", (pid,)).fetchone()
                if not row or row["stock"] < q:
                    raise ValueError(f"Not enough stock for {row['name'] if row else 'item'}.")
            for pid, q in need.items():
                s.c.execute("UPDATE products SET stock=stock-? WHERE id=?", (q, pid))
            total = sum(i["qty"] * i["price"] for i in items)
            cur = s.c.execute("INSERT INTO orders(created,customer,priority,total) VALUES(?,?,?,?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), customer, priority, total))
            s.c.executemany("INSERT INTO order_items VALUES(?,?,?,?,?)",
                            [(cur.lastrowid, i["name"], i["size"], i["qty"], i["price"]) for i in items])
            return cur.lastrowid, total

    def pending(s): return [dict(r) for r in s.c.execute("SELECT * FROM orders WHERE status='pending'")]
    def order(s, oid): return dict(s.c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone())

    def items_text(s, oid):
        rows = s.c.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()
        return ", ".join(f"{r['qty']}x {r['name']}" + (f" ({r['size']})" if r["size"] else "") for r in rows)

    def complete(s, oid):
        with s.c: s.c.execute("UPDATE orders SET status='served' WHERE id=?", (oid,))

    def history(s): return [dict(r) for r in s.c.execute("SELECT * FROM orders ORDER BY id DESC")]


# ======================= UI =======================
def peso(x): return f"₱{x:,.2f}"


class App(tk.Tk):
    def __init__(s):
        super().__init__()
        s.title("Gulps & Grubs at the Garage - POS")
        s.geometry("1200x740"); s.minsize(1100, 680)
        s.configure(bg=YELLOW)
        s.db, s.avl, s.heap = Database(), AVLTree(), MinHeap()
        s.reload_products(); s.reload_heap()
        s.body = tk.Frame(s, bg=ORANGE); s.body.pack(fill="both", expand=True, padx=8, pady=8)
        st = ttk.Style(s); st.theme_use("clam")
        st.configure("Treeview", background=CREAM, fieldbackground=CREAM, foreground=BROWN, rowheight=28, font=(FONT, 11))
        st.configure("Treeview.Heading", background=BROWN, foreground=CREAM, font=(FONT, 11, "bold"))
        st.map("Treeview", background=[("selected", YELLOW)], foreground=[("selected", BROWN)])
        st.configure("TNotebook", background=ORANGE, borderwidth=0)
        st.configure("TNotebook.Tab", background=CREAM, foreground=BROWN, font=(FONT, 12, "bold"), padding=(20, 8))
        st.map("TNotebook.Tab", background=[("selected", YELLOW)])
        s.show_login()

    # ---------- helpers ----------
    def reload_products(s):
        s.avl = AVLTree()
        for p in s.db.products(): s.avl.insert(p["name"].lower(), p)
        s.by_id = {p["id"]: p for p in s.avl.inorder()}

    def reload_heap(s):
        s.heap = MinHeap()
        for o in s.db.pending(): s.heap.push((o["priority"], o["id"]))

    def clear(s):
        for w in s.body.winfo_children(): w.destroy()

    def logo(s, parent, w, h, size, lines, bubbles=True):
        c = tk.Canvas(parent, width=w, height=h, bg=ORANGE, highlightthickness=0)
        if bubbles:
            for _ in range(40):
                x, y, r = random.randint(0, w), random.randint(int(h * .15), int(h * .85)), random.randint(4, 16)
                c.create_oval(x - r, y - r, x + r, y + r, fill=BUBBLE, outline="")
        step = h / (len(lines) + 0)
        for i, (txt, sz) in enumerate(lines):
            y = step * (i + .5)
            for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 4), (0, -3), (-4, 0), (4, 0)]:
                c.create_text(w / 2 + dx, y + dy, text=txt, fill=BROWN, font=(FONT, sz, "bold"))
            c.create_text(w / 2, y, text=txt, fill=CREAM, font=(FONT, sz, "bold"))
        return c

    def btn(s, parent, text, cmd, bg=BROWN, fg=CREAM, w=None, size=12):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=YELLOW, activeforeground=BROWN,
                         font=(FONT, size, "bold"), relief="flat", bd=0, padx=14, pady=8, width=w, cursor="hand2")

    def card(s, parent):
        return tk.Frame(parent, bg=CREAM, highlightbackground=BROWN, highlightthickness=3)

    def lbl(s, parent, text, size=11, bold=True, bg=CREAM, fg=BROWN):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, size, "bold" if bold else "normal"))

    def entry(s, parent, var=None, w=18):
        return tk.Entry(parent, textvariable=var, width=w, font=(FONT, 12), bg="white", fg=BROWN, relief="solid", bd=1)

    def header(s, mode):
        h = tk.Frame(s.body, bg=ORANGE); h.pack(fill="x", padx=14, pady=(10, 0))
        s.logo(h, 430, 70, 20, [("Gulps & Grubs at the Garage", 20)], bubbles=False).pack(side="left")
        s.btn(h, "⟵ Switch Mode", s.show_login, bg=CREAM, fg=BROWN).pack(side="right")
        s.lbl(h, f"{mode} MODE", 16, bg=ORANGE, fg=CREAM).pack(side="right", padx=20)

    def tree(s, parent, cols, widths, h=14):
        t = ttk.Treeview(parent, columns=cols, show="headings", height=h)
        for c, w in zip(cols, widths):
            t.heading(c, text=c); t.column(c, width=w, anchor="w" if c in ("Name", "Item", "Items", "Customer") else "center")
        return t

    # ---------- login / mode select ----------
    def show_login(s):
        s.clear()
        s.logo(s.body, 640, 240, 40, [("Gulps & Grubs", 44), ("at the", 16), ("Garage", 44)]).pack(pady=(40, 10))
        s.lbl(s.body, "Choose your mode", 16, bg=ORANGE, fg=CREAM).pack(pady=10)
        row = tk.Frame(s.body, bg=ORANGE); row.pack(pady=10)
        for txt, cmd in [("🧾  CASHIER", s.show_cashier), ("🍔  KITCHEN", s.show_kitchen), ("🔧  ADMIN", s.admin_login)]:
            s.btn(row, txt, cmd, w=14, size=18).pack(side="left", padx=14, ipady=14)

    def admin_login(s):
        pin = simpledialog.askstring("Admin", "Enter admin PIN:", show="*", parent=s)
        if pin == ADMIN_PIN: s.show_admin()
        elif pin is not None: messagebox.showerror("Denied", "Wrong PIN.")

    # ---------- CASHIER ----------
    def show_cashier(s):
        s.clear(); s.header("CASHIER"); s.cart = CartList()
        main = tk.Frame(s.body, bg=ORANGE); main.pack(fill="both", expand=True, padx=14, pady=10)
        left, right = s.card(main), s.card(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8)); right.pack(side="left", fill="both", expand=True)

        # left: menu
        s.lbl(left, "MENU  (AVL search - type the start of a name)", 12).pack(anchor="w", padx=10, pady=(8, 2))
        s.q = tk.StringVar(); s.entry(s.q, 30) if False else None
        e = s.entry(left, s.q, 34); e.pack(anchor="w", padx=10); s.q.trace_add("write", lambda *a: s.fill_menu())
        s.menu = s.tree(left, ("Name", "Category", "Price", "Stock"), (210, 90, 90, 70), 13)
        s.menu.pack(fill="both", expand=True, padx=10, pady=8)
        opt = tk.Frame(left, bg=CREAM); opt.pack(fill="x", padx=10)
        s.lbl(opt, "Drink size:").pack(side="left")
        s.size_var = tk.StringVar(value="Small"); s.size_btns = []
        for z in s.db.sizes():
            r = tk.Radiobutton(opt, text=f"{z['name']} (+{peso(z['extra'])})", variable=s.size_var, value=z["name"],
                               bg=CREAM, fg=BROWN, selectcolor=YELLOW, activebackground=CREAM, font=(FONT, 10, "bold"))
            r.pack(side="left", padx=6); s.size_btns.append(r)
        opt2 = tk.Frame(left, bg=CREAM); opt2.pack(fill="x", padx=10, pady=8)
        s.lbl(opt2, "Qty:").pack(side="left")
        s.qty = tk.Spinbox(opt2, from_=1, to=99, width=4, font=(FONT, 12)); s.qty.pack(side="left", padx=6)
        s.btn(opt2, "＋ Add to Cart", s.add_to_cart, bg=BROWN).pack(side="right")
        s.menu.bind("<<TreeviewSelect>>", lambda e: s.toggle_sizes())
        s.fill_menu()

        # right: cart
        s.lbl(right, "CART  (Linked List)", 12).pack(anchor="w", padx=10, pady=(8, 2))
        s.cart_t = s.tree(right, ("Item", "Size", "Qty", "Price", "Subtotal"), (170, 70, 50, 80, 90), 12)
        s.cart_t.pack(fill="both", expand=True, padx=10, pady=8)
        bar = tk.Frame(right, bg=CREAM); bar.pack(fill="x", padx=10)
        s.btn(bar, "Remove Selected", s.remove_item, bg=YELLOW, fg=BROWN, size=10).pack(side="left")
        s.btn(bar, "Clear Cart", lambda: (s.cart.clear(), s.fill_cart()), bg=YELLOW, fg=BROWN, size=10).pack(side="left", padx=6)
        f = tk.Frame(right, bg=CREAM); f.pack(fill="x", padx=10, pady=8)
        s.lbl(f, "Customer:").grid(row=0, column=0, sticky="w")
        s.cust = tk.StringVar(); s.entry(f, s.cust, 16).grid(row=0, column=1, padx=6, pady=2)
        s.lbl(f, "Priority:").grid(row=1, column=0, sticky="w")
        s.prio = ttk.Combobox(f, values=list(PRIORITY.values()), state="readonly", width=14, font=(FONT, 11))
        s.prio.current(1); s.prio.grid(row=1, column=1, padx=6, pady=2)
        s.total_lbl = s.lbl(right, "TOTAL: ₱0.00", 20); s.total_lbl.pack(pady=4)
        s.btn(right, "✔  CHECKOUT", s.checkout, bg=BROWN, size=16).pack(fill="x", padx=10, pady=(0, 10))

    def fill_menu(s):
        s.menu.delete(*s.menu.get_children())
        q = s.q.get().strip().lower()
        for p in (s.avl.prefix(q) if q else s.avl.inorder()):
            s.menu.insert("", "end", iid=str(p["id"]), values=(p["name"], p["category"], peso(p["price"]), p["stock"]))
        s.toggle_sizes()

    def toggle_sizes(s):
        sel = s.menu.selection()
        on = bool(sel) and s.by_id[int(sel[0])]["has_sizes"]
        for r in s.size_btns: r.configure(state="normal" if on else "disabled")

    def add_to_cart(s):
        sel = s.menu.selection()
        if not sel: return messagebox.showinfo("Pick an item", "Select a menu item first.")
        p = s.by_id[int(sel[0])]
        try:
            q = int(s.qty.get()); assert q > 0
        except Exception:
            return messagebox.showerror("Invalid", "Quantity must be a positive whole number.")
        if s.cart.qty_of(p["id"]) + q > p["stock"]:
            return messagebox.showwarning("Stock", f"Only {p['stock']} of {p['name']} in stock.")
        size, price = "", p["price"]
        if p["has_sizes"]:
            size = s.size_var.get()
            price += next(z["extra"] for z in s.db.sizes() if z["name"] == size)
        s.cart.add({"pid": p["id"], "name": p["name"], "size": size, "qty": q, "price": price})
        s.fill_cart()

    def fill_cart(s):
        s.cart_t.delete(*s.cart_t.get_children())
        for i in s.cart:
            s.cart_t.insert("", "end", iid=f"{i['pid']}|{i['size']}",
                            values=(i["name"], i["size"] or "-", i["qty"], peso(i["price"]), peso(i["qty"] * i["price"])))
        s.total_lbl.config(text=f"TOTAL: {peso(s.cart.total())}")

    def remove_item(s):
        for iid in s.cart_t.selection():
            pid, size = iid.split("|", 1); s.cart.remove(int(pid), size)
        s.fill_cart()

    def checkout(s):
        if s.cart.size == 0: return messagebox.showinfo("Empty", "Cart is empty.")
        prio = int(s.prio.get()[0]); cust = s.cust.get().strip() or "Walk-in"
        items = list(s.cart)
        try:
            oid, total = s.db.checkout(items, prio, cust)
        except ValueError as e:
            return messagebox.showerror("Stock", str(e))
        s.heap.push((prio, oid))
        lines = [f"Order #{oid:04d}   ({PRIORITY[prio]})", f"Customer: {cust}", "-" * 34]
        lines += [f"{i['qty']}x {i['name']} {i['size']}".strip() + f"  {peso(i['qty'] * i['price'])}" for i in items]
        lines += ["-" * 34, f"TOTAL: {peso(total)}"]
        messagebox.showinfo("Receipt", "\n".join(lines))
        s.cart.clear(); s.cust.set(""); s.reload_products(); s.fill_cart(); s.fill_menu()

    # ---------- KITCHEN ----------
    def show_kitchen(s):
        s.clear(); s.header("KITCHEN")
        c = s.card(s.body); c.pack(fill="both", expand=True, padx=14, pady=10)
        s.now = s.lbl(c, "", 18); s.now.pack(pady=(12, 4))
        s.lbl(c, "Pending orders (Min-Heap: Rush first, then oldest)", 11, bold=False).pack()
        s.kt = s.tree(c, ("Order", "Priority", "Customer", "Items", "Total"), (80, 100, 140, 520, 100), 14)
        s.kt.pack(fill="both", expand=True, padx=12, pady=10)
        s.btn(c, "🔔  SERVE NEXT ORDER", s.serve_next, size=16).pack(pady=(0, 12))
        s.fill_kitchen()

    def fill_kitchen(s):
        s.kt.delete(*s.kt.get_children())
        for pr, oid in s.heap.sorted_items():
            o = s.db.order(oid)
            s.kt.insert("", "end", values=(f"#{oid:04d}", PRIORITY[pr], o["customer"], s.db.items_text(oid), peso(o["total"])))
        top = s.heap.peek()
        s.now.config(text=f"NEXT UP: #{top[1]:04d}  ({PRIORITY[top[0]]})" if top else "No pending orders 🎉")

    def serve_next(s):
        top = s.heap.pop()
        if top: s.db.complete(top[1])
        s.fill_kitchen()

    # ---------- ADMIN ----------
    def show_admin(s):
        s.clear(); s.header("ADMIN")
        nb = ttk.Notebook(s.body); nb.pack(fill="both", expand=True, padx=14, pady=10)
        t1, t2, t3 = [tk.Frame(nb, bg=CREAM) for _ in range(3)]
        nb.add(t1, text="Products"); nb.add(t2, text="Drink Sizes"); nb.add(t3, text="Sales History")

        # --- products ---
        left = tk.Frame(t1, bg=CREAM); left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        s.aq = tk.StringVar(); s.lbl(left, "Search (AVL):").pack(anchor="w")
        s.entry(left, s.aq, 30).pack(anchor="w"); s.aq.trace_add("write", lambda *a: s.fill_admin())
        s.pt = s.tree(left, ("Name", "Category", "Price", "Stock", "Sizes"), (200, 80, 90, 70, 70), 16)
        s.pt.pack(fill="both", expand=True, pady=8); s.pt.bind("<<TreeviewSelect>>", s.pick_product)
        s.avl_lbl = s.lbl(left, "", 10, bold=False); s.avl_lbl.pack(anchor="w")
        form = s.card(t1); form.pack(side="left", fill="y", padx=10, pady=10)
        s.f_name, s.f_price, s.f_stock = tk.StringVar(), tk.StringVar(), tk.StringVar()
        s.f_cat, s.f_size = tk.StringVar(value="Drink"), tk.IntVar(value=1)
        for r, (t, v) in enumerate([("Name", s.f_name), ("Price (₱)", s.f_price), ("Stock", s.f_stock)]):
            s.lbl(form, t).grid(row=r, column=0, sticky="w", padx=10, pady=6); s.entry(form, v, 16).grid(row=r, column=1, padx=10)
        s.lbl(form, "Category").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        ttk.Combobox(form, textvariable=s.f_cat, values=["Drink", "Food"], state="readonly", width=14).grid(row=3, column=1)
        tk.Checkbutton(form, text="Has size options (S/M/L)", variable=s.f_size, bg=CREAM, fg=BROWN, selectcolor=YELLOW,
                       activebackground=CREAM, font=(FONT, 10, "bold")).grid(row=4, column=0, columnspan=2, pady=6)
        for r, (t, cmd) in enumerate([("Add", s.p_add), ("Update", s.p_update), ("Delete", s.p_delete)]):
            s.btn(form, t, cmd, w=16).grid(row=5 + r, column=0, columnspan=2, pady=5, padx=10)
        s.fill_admin()

        # --- sizes ---
        s.lbl(t2, "Extra charge added to the base price of size-enabled drinks", 13).pack(pady=(20, 10))
        s.size_vars = {}
        for z in s.db.sizes():
            r = tk.Frame(t2, bg=CREAM); r.pack(pady=6)
            s.lbl(r, z["name"], 13).pack(side="left", padx=10)
            v = tk.StringVar(value=str(z["extra"])); s.size_vars[z["name"]] = v; s.entry(r, v, 8).pack(side="left")
        s.btn(t2, "Save Sizes", s.save_sizes).pack(pady=14)

        # --- history ---
        ht = s.tree(t3, ("Order", "Date", "Customer", "Priority", "Status", "Total"), (80, 150, 150, 100, 90, 110), 18)
        ht.pack(fill="both", expand=True, padx=10, pady=10); gross = 0
        for o in s.db.history():
            gross += o["total"]
            ht.insert("", "end", values=(f"#{o['id']:04d}", o["created"], o["customer"], PRIORITY[o["priority"]], o["status"], peso(o["total"])))
        s.lbl(t3, f"Total sales: {peso(gross)}", 14).pack(pady=(0, 10))

    def fill_admin(s):
        s.pt.delete(*s.pt.get_children())
        q = s.aq.get().strip().lower()
        for p in (s.avl.prefix(q) if q else s.avl.inorder()):
            s.pt.insert("", "end", iid=str(p["id"]),
                        values=(p["name"], p["category"], peso(p["price"]), p["stock"], "Yes" if p["has_sizes"] else "-"))
        s.avl_lbl.config(text=f"AVL tree height: {s.avl.height()}  |  products: {len(s.by_id)}")

    def pick_product(s, _=None):
        sel = s.pt.selection()
        if not sel: return
        p = s.by_id[int(sel[0])]
        s.f_name.set(p["name"]); s.f_price.set(p["price"]); s.f_stock.set(p["stock"])
        s.f_cat.set(p["category"]); s.f_size.set(p["has_sizes"])

    def read_form(s):
        name = s.f_name.get().strip()
        try:
            price, stock = float(s.f_price.get()), int(s.f_stock.get())
            assert name and price >= 0 and stock >= 0
        except Exception:
            messagebox.showerror("Invalid", "Enter a name, a price (number ≥ 0) and a stock (whole number ≥ 0).")
            return None
        return name, s.f_cat.get(), price, stock, s.f_size.get() if s.f_cat.get() == "Drink" else 0

    def after_change(s): s.reload_products(); s.fill_admin()

    def p_add(s):
        d = s.read_form()
        if d:
            try: s.db.add_product(*d); s.after_change()
            except sqlite3.IntegrityError: messagebox.showerror("Duplicate", "A product with that name already exists.")

    def p_update(s):
        sel = s.pt.selection(); d = s.read_form()
        if sel and d:
            try: s.db.update_product(int(sel[0]), *d); s.after_change()
            except sqlite3.IntegrityError: messagebox.showerror("Duplicate", "A product with that name already exists.")

    def p_delete(s):
        sel = s.pt.selection()
        if sel and messagebox.askyesno("Delete", "Delete this product?"):
            s.db.delete_product(int(sel[0])); s.after_change()

    def save_sizes(s):
        try:
            d = {n: float(v.get()) for n, v in s.size_vars.items()}; assert all(x >= 0 for x in d.values())
        except Exception:
            return messagebox.showerror("Invalid", "Size prices must be numbers ≥ 0.")
        s.db.save_sizes(d); messagebox.showinfo("Saved", "Size prices updated.")


if __name__ == "__main__":
    App().mainloop()
