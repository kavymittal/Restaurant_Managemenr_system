import os
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Egainagra99",  # Update with your MySQL password
    "database": "restaurant_db"
}

@contextmanager
def get_db_cursor(dictionary=True):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cursor
    finally:
        cursor.close()
        conn.close()

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Simple hardcoded admin check or query employee table
        if username == "admin" and password == "admin123":
            session["admin"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with get_db_cursor(dictionary=False) as (conn, cursor):
        cursor.execute("SELECT COUNT(*) FROM customer")
        customers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM menu_item")
        items = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders")
        orders = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payment")
        revenue = cursor.fetchone()[0]

    return render_template(
        "dashboard.html",
        customers=customers,
        items=items,
        orders=orders,
        revenue=revenue
    )

@app.route("/menu", methods=["GET", "POST"])
@login_required
def menu():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        price_str = request.form.get("price", "0")

        try:
            price = Decimal(price_str)
            with get_db_cursor() as (conn, cursor):
                cursor.execute("""
                    INSERT INTO menu_item (category_id, item_name, price)
                    VALUES (%s, %s, %s)
                """, (category_id, name, price))
                conn.commit()
            flash("Menu item added successfully")
        except InvalidOperation:
            flash("Invalid price value entered")

    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("""
            SELECT m.*, c.category_name 
            FROM menu_item m
            LEFT JOIN menu_category c ON m.category_id = c.category_id
            ORDER BY m.item_id
        """)
        items = cursor.fetchall()

        cursor.execute("SELECT * FROM menu_category")
        categories = cursor.fetchall()

    return render_template("menu.html", items=items, categories=categories)
@app.route("/delete_menu/<int:item_id>")
@login_required
def delete_menu(item_id):
    with get_db_cursor() as (conn, cursor):
        try:
            cursor.execute("DELETE FROM menu_item WHERE item_id = %s", (item_id,))
            conn.commit()
            flash("Menu item deleted")
        except mysql.connector.Error:
            conn.rollback()
            flash("Cannot delete an item that is already linked to an order")
    return redirect(url_for("menu"))

@app.route("/toggle_menu/<int:item_id>")
@login_required
def toggle_menu(item_id):
    with get_db_cursor() as (conn, cursor):
        cursor.execute("""
            UPDATE menu_item
            SET is_available = NOT is_available
            WHERE item_id = %s
        """, (item_id,))
        conn.commit()
    flash("Availability updated")
    return redirect(url_for("menu"))

@app.route("/customers", methods=["GET", "POST"])
@login_required

def customers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()

        with get_db_cursor() as (conn, cursor):
            cursor.execute("""
                INSERT INTO customer (name, phone, email)
                VALUES (%s, %s, %s)
            """, (name, phone, email))
            conn.commit()
        flash("Customer added successfully")

    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM customer ORDER BY customer_id")
        data = cursor.fetchall()

    return render_template("customers.html", customers=data)

@app.route("/new_order", methods=["GET", "POST"])
@login_required
def new_order():
    if request.method == "POST":
        customer_id = request.form.get("customer_id") or None
        table_id = request.form.get("table_id") or None
        emp_id = request.form.get("emp_id") or None
        discount_str = request.form.get("discount", "0.00")
        item_ids = request.form.getlist("item_id")
        quantities = request.form.getlist("quantity")
        payment_method = request.form.get("payment_method", "Cash")

        try:
            discount = Decimal(discount_str)
            with get_db_cursor(dictionary=True) as (conn, cursor):
                # 1. Create order record with discount
                cursor.execute("""
                    INSERT INTO orders (customer_id, table_id, emp_id, discount, status)
                    VALUES (%s, %s, %s, %s, 'Placed')
                """, (customer_id, table_id, emp_id, discount))
                order_id = cursor.lastrowid

                # 2. Update Dining Table status to 'Occupied'
                if table_id:
                    cursor.execute("UPDATE dining_table SET status = 'Occupied' WHERE table_id = %s", (table_id,))

                # 3. Insert items into order_item (Triggers handle line_total, subtotal, and 5% GST automatically)
                for item_id, qty_str in zip(item_ids, quantities):
                    qty = int(qty_str)
                    cursor.execute("""
                        INSERT INTO order_item (order_id, item_id, quantity, line_total)
                        VALUES (%s, %s, %s, 0)
                    """, (order_id, item_id, qty))

                # Fetch updated total amount calculated by MySQL Trigger
                cursor.execute("SELECT total_amount FROM orders WHERE order_id = %s", (order_id,))
                total_amount = cursor.fetchone()["total_amount"]

                # 4. Insert payment
                cursor.execute("""
                    INSERT INTO payment (order_id, emp_id, amount_paid, mode)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, emp_id, total_amount, payment_method))

                conn.commit()
                flash(f"Order #{order_id} placed! Subtotal + 5% GST - Discount = Final Bill: ₹{total_amount}")
                return redirect(url_for("orders"))

        except (ValueError, TypeError, mysql.connector.Error) as e:
            flash(f"Order Failed: {e}")
            return redirect(url_for("new_order"))

    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM customer ORDER BY name")
        customers_list = cursor.fetchall()

        cursor.execute("SELECT * FROM dining_table WHERE status = 'Available'")
        tables_list = cursor.fetchall()

        cursor.execute("SELECT * FROM employee WHERE role = 'Waiter'")
        waiters_list = cursor.fetchall()

        cursor.execute("SELECT * FROM menu_item WHERE is_available = TRUE ORDER BY item_name")
        menu_list = cursor.fetchall()

    return render_template(
        "new_order.html",
        customers=customers_list,
        tables=tables_list,
        waiters=waiters_list,
        menu=menu_list
    )

@app.route("/orders")
@login_required
def orders():
    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("""
            SELECT o.order_id, c.name AS customer_name, t.table_id, e.name AS waiter_name,
                   o.order_time, o.subtotal, o.gst, o.discount, o.total_amount, o.status
            FROM orders o
            JOIN customer c ON o.customer_id = c.customer_id
            LEFT JOIN dining_table t ON o.table_id = t.table_id
            LEFT JOIN employee e ON o.emp_id = e.emp_id
            ORDER BY o.order_id DESC
        """)
        data = cursor.fetchall()

    return render_template("orders.html", orders=data)

@app.route("/bill/<int:order_id>")
@login_required
def bill(order_id):
    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("""
            SELECT o.*, c.name AS customer_name, c.phone, e.name AS waiter_name
            FROM orders o
            JOIN customer c ON o.customer_id = c.customer_id
            LEFT JOIN employee e ON o.emp_id = e.emp_id
            WHERE o.order_id = %s
        """, (order_id,))
        order_info = cursor.fetchone()

        if not order_info:
            return "Order not found", 404

        cursor.execute("""
            SELECT m.item_name, oi.quantity, m.price, oi.line_total
            FROM order_item oi
            JOIN menu_item m ON oi.item_id = m.item_id
            WHERE oi.order_id = %s
        """, (order_id,))
        details = cursor.fetchall()

        cursor.execute("SELECT mode FROM payment WHERE order_id = %s LIMIT 1", (order_id,))
        pay_info = cursor.fetchone()

    return render_template(
        "bill.html",
        order=order_info,
        details=details,
        payment=pay_info
    )

@app.route("/complete_order/<int:order_id>")
@login_required

def complete_order(order_id):
    with get_db_cursor() as (conn, cursor):
        # Fetch the table_id as a dictionary key
        cursor.execute("SELECT table_id FROM orders WHERE order_id = %s", (order_id,))
        res = cursor.fetchone()
        
        # Access it using the column name instead of [0]
        if res and res["table_id"]:
            cursor.execute("UPDATE dining_table SET status = 'Available' WHERE table_id = %s", (res["table_id"],))

        cursor.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s", (order_id,))
        conn.commit()

    flash("Order completed and table freed!")
    return redirect(url_for("orders"))
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)