DROP DATABASE IF EXISTS restaurant_db;
CREATE DATABASE restaurant_db;
USE restaurant_db;

-- 1. MENU CATEGORY
CREATE TABLE menu_category (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE
);

-- 2. MENU ITEM
CREATE TABLE menu_item (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT,
    item_name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES menu_category(category_id) ON DELETE SET NULL
);

-- 3. CUSTOMER
CREATE TABLE customer (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(15) NOT NULL UNIQUE,
    email VARCHAR(100),
    registered_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. EMPLOYEE
CREATE TABLE employee (
    emp_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    phone VARCHAR(15)
);

-- 5. DINING TABLE
CREATE TABLE dining_table (
    table_id INT AUTO_INCREMENT PRIMARY KEY,
    seats INT NOT NULL,
    status VARCHAR(20) DEFAULT 'Available' CHECK (status IN ('Available', 'Occupied', 'Reserved'))
);

-- 6. ORDERS
CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    table_id INT,
    emp_id INT,
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(10,2) DEFAULT 0.00,
    gst DECIMAL(10,2) DEFAULT 0.00,
    discount DECIMAL(10,2) DEFAULT 0.00,
    total_amount DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(30) DEFAULT 'Placed' CHECK (status IN ('Placed', 'Served', 'Paid', 'Cancelled')),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (table_id) REFERENCES dining_table(table_id),
    FOREIGN KEY (emp_id) REFERENCES employee(emp_id)
);

-- 7. ORDER ITEM
CREATE TABLE order_item (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    line_total DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES menu_item(item_id)
);

-- 8. PAYMENT
CREATE TABLE payment (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    emp_id INT,
    pay_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    amount_paid DECIMAL(10,2) NOT NULL,
    mode VARCHAR(30) CHECK (mode IN ('Cash', 'UPI', 'Card')),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (emp_id) REFERENCES employee(emp_id)
);

-- TRIGGERS
DELIMITER //

CREATE TRIGGER trg_calc_line_total
BEFORE INSERT ON order_item
FOR EACH ROW
BEGIN
    DECLARE item_price DECIMAL(10,2);
    SELECT price INTO item_price FROM menu_item WHERE item_id = NEW.item_id;
    SET NEW.line_total = item_price * NEW.quantity;
END //

CREATE TRIGGER trg_update_order_totals
AFTER INSERT ON order_item
FOR EACH ROW
BEGIN
    DECLARE sub DECIMAL(10,2);
    DECLARE calc_gst DECIMAL(10,2);
    DECLARE disc DECIMAL(10,2);
    
    SELECT COALESCE(SUM(line_total), 0) INTO sub FROM order_item WHERE order_id = NEW.order_id;
    SELECT discount INTO disc FROM orders WHERE order_id = NEW.order_id;
    
    SET calc_gst = sub * 0.05;
    
    UPDATE orders 
    SET subtotal = sub,
        gst = calc_gst,
        total_amount = (sub + calc_gst - disc)
    WHERE order_id = NEW.order_id;
END //

DELIMITER ;

-- SEED DATA
INSERT INTO menu_category (category_id, category_name) VALUES (1, 'Main Course'), (2, 'Breads'), (3, 'Beverages'), (4, 'Dessert');
INSERT INTO menu_item (item_id, category_id, item_name, price) VALUES (1, 1, 'Paneer Butter Masala', 250.00), (2, 2, 'Butter Naan', 40.00), (3, 3, 'Cold Drink', 60.00), (4, 4, 'Gulab Jamun', 50.00);
INSERT INTO customer (customer_id, name, phone, email) VALUES (1, 'Rahul Sharma', '9876543210', 'rahul@gmail.com'), (2, 'Priya Verma', '9876543211', 'priya@gmail.com');
INSERT INTO employee (emp_id, name, role, phone) VALUES (1, 'Aman Singh', 'Waiter', '9998887771'), (2, 'Admin User', 'Manager', '9998887772');
INSERT INTO dining_table (table_id, seats, status) VALUES (1, 4, 'Available'), (2, 2, 'Available'), (3, 6, 'Available');
