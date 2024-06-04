from flask import Flask, render_template, redirect, url_for, request, session, flash,jsonify
import sqlite3
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import random
from fpdf import FPDF
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/images'
app.static_folder = 'static'

def secure_filename(filename):
    filename = re.sub(r'[^\w\s.-]', '', filename)
    return filename

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript('''
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS cart;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0, 1))
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT NOT NULL,
            details TEXT 
        );

        CREATE TABLE cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        CREATE TABLE contact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email REAL NOT NULL,
            mobile_no INTEGER NOT NULL,
            message TEXT NOT NULL,
            Type_of_inquiry TEXT not NULL
        );

        INSERT INTO users (username, password, is_admin) VALUES
            ('admin', 'admin', 1),
            ('user', 'user', 0);
                       
    ''')
    conn.commit()
    conn.close()

if not os.path.exists('database.db'):
    init_db()

@app.before_request
def before_request():
    allowed_routes = ['login', 'logout', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def home():
    return render_template('user_home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            if user['is_admin']:
                return redirect(url_for('admin_home'))
            else:
                return redirect(url_for('user_home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    return redirect(url_for('login'))
from flask import render_template, redirect, url_for, request, session
import sqlite3

@app.route('/user_home')
def user_home():
    try:
        # Connect to the database
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Fetch the three most recent products
        cursor.execute('SELECT * FROM products ORDER BY id DESC LIMIT 3')
        recent_products = cursor.fetchall()

        # Close the database connection
        conn.close()

        # Convert tuple of tuples to list of dictionaries
        recent_products = [{'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3], 'quantity': row[4], 'image': row[5], 'details': row[6]} for row in recent_products]

        # Render the template with the recent products
        return render_template('user_home.html', recent_products=recent_products)

    except Exception as e:
        # Handle any errors that occur during database operation
        print("An error occurred:", str(e))
        # Redirect to an error page or handle the error as appropriate
        return render_template('error.html', error_message="An error occurred while fetching recent products.")

@app.route('/admin_home')
def admin_home():
   
    return render_template('admin_home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/products', methods=['GET', 'POST'])
def products():
    conn = get_db_connection()
    if request.method == 'POST':
        category = request.form.get('categories')  # <--- Change here
        if category:
            products = conn.execute('SELECT * FROM products WHERE category =?', (category,)).fetchall()
        else:
            products = conn.execute('SELECT * FROM products').fetchall()
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    else:
        products = conn.execute('SELECT * FROM products').fetchall()
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    conn.close()
    return render_template('products.html', products=products, categories=categories)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    categories = ['Skin Care', 'Body Care', 'Hair Care', 'Others']

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        quantity = request.form['quantity']
        category = request.form['category']
        details = request.form['details']
        new_category = request.form.get('new_category')
        image = request.files.get('image')

        if category == 'Others' and new_category:
            category = new_category
            if new_category not in categories:
                categories.append(new_category)

        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
        else:
            image_path = None

        if image_path:
            image_name = os.path.basename(image_path)

        conn = get_db_connection()
        conn.execute('INSERT INTO products (name, price, quantity, category, image, details) VALUES (?, ?, ?, ?, ?, ?)',
                     (name, price, quantity, category, image_name, details))
        conn.commit()
        conn.close()

        return redirect(url_for('add_product'))

    return render_template('add_product.html', categories=categories)

@app.route('/cart')
def cart():  
    conn = get_db_connection()
    cart_items = conn.execute('''
        SELECT c.id, p.name, p.price, c.quantity, p.category, p.image, p.details, p.quantity AS available_quantity
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/manage_products')
def manage_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('manage_products.html', products=products)

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product(id):
    name = request.form['name']
    price = request.form['price']
    category = request.form['category']
    quantity = request.form['quantity']
    details = request.form['details']
    image = request.files.get('image')

    conn = get_db_connection()

    if image:
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        image_name = os.path.basename(image_path)
        conn.execute('UPDATE products SET name = ?, price = ?, category = ?, quantity = ?, details = ?, image = ? WHERE id = ?', 
                     (name, price, category, quantity, details, image_name, id))
    else:
        conn.execute('UPDATE products SET name = ?, price = ?, category = ?, quantity = ?, details = ? WHERE id = ?', 
                     (name, price, category, quantity, details, id))
                     
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))

@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    conn = get_db_connection()
    user_id = session['user_id']

    product = conn.execute('SELECT * FROM products WHERE id =?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.')
        return redirect(url_for('products'))

    cart_item = conn.execute('SELECT * FROM cart WHERE user_id =? AND product_id =?', (user_id, product_id)).fetchone()
    
    if cart_item:
        new_quantity = cart_item['quantity'] 
        if product['quantity']==0:
            flash('Not enough stock available.')
            return redirect(url_for('products'))
        conn.execute('UPDATE cart SET quantity =? WHERE user_id =? AND product_id =?', (new_quantity+1, user_id, product_id))
        product_quantity=new_quantity
    else:
        if product['quantity'] == 0:
            flash('Not enough stock available.')
            return redirect(url_for('products'))
        conn.execute('INSERT INTO cart (user_id, product_id, name, price, category, quantity, image, details) VALUES (?,?,?,?,?,?,?,?)',
                     (user_id, product_id, product['name'], product['price'], product['category'], 1, product['image'], product['details']))
    conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (product['quantity'] - 1, product_id))

    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):

    conn = get_db_connection()
    user_id = session['user_id']
    
    try:
        # Fetch the cart item
        cart_item = conn.execute('SELECT * FROM cart WHERE user_id = ? AND product_id = ?', (user_id, product_id)).fetchone()
        
        if cart_item:
            current_quantity = cart_item['quantity']
            if current_quantity > 0:
                # Decrease the quantity in the cart
                conn.execute('UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?', (current_quantity - 1, user_id, product_id))
  
            # Update the product quantity in the products table
            product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if product:
                product_quantity = product['quantity']
                conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (product_quantity + 1, product_id))
            print("Current cart quantity:", current_quantity)
            print("Product quantity in stock:", product_quantity)

        conn.commit()
    except sqlite3.Error as e:
        print("An error occurred:", e.args[0])
        conn.rollback()
    finally:
        conn.close()
    
    return redirect(url_for('cart'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile_no = request.form['mobile']
        message = request.form['message']
        type_of_inquiry = request.form['query_type']
        conn = get_db_connection()
        conn.execute('INSERT INTO contact (name, email, mobile_no, message, Type_of_inquiry) VALUES (?, ?, ?, ?, ?)',
                     (name, email, mobile_no, message, type_of_inquiry))
        print(mobile_no,email,message,type_of_inquiry)
        
        conn.commit()
        conn.close()
      
        flash('Your message has been sent successfully!')
        return redirect(url_for('contact'))

    return render_template('contact.html')
@app.route('/inquiries')
def inquiries():
    # Connect to the database
    conn = get_db_connection()

    # Fetch all inquiries
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contact')
    inquiries = cursor.fetchall()

    # Close the database connection
    conn.close()

    # Render the HTML template with the fetched inquiries
    return render_template('inquiries.html', inquiries=inquiries)



@app.route('/delete_inquiry/<int:id>', methods=['POST'])
def delete_inquiry(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Delete the inquiry with the specified id
    cursor.execute('DELETE FROM contact WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash('Inquiry deleted successfully!')
    return redirect(url_for('inquiries'))

def generate_invoice_number():
    # Generate a random invoice number (you can modify this according to your needs)
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))


def generate_invoice(invoice_number, items):
    # Directory to save the invoice PDF
    directory = 'static'

    # Create the directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Generate invoice content
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Invoice", ln=True, align="C")
    pdf.cell(200, 10, txt=f"Invoice Number: {invoice_number}", ln=True, align="L")
    pdf.cell(200, 10, txt="", ln=True)  # Add an empty line for spacing
    pdf.cell(200, 10, txt="Items Bought:", ln=True, align="L")
    for item in items:
        pdf.cell(200, 10, txt=f"- {item}", ln=True, align="L")
    pdf_file_path = f"{directory}/{invoice_number}.pdf"
    pdf.output(pdf_file_path)
    return pdf_file_path

@app.route('/send_confirmation', methods=['POST','GET'])
def send_confirmation():
    if request.method == 'POST':
        email = request.json.get('email')
        items = request.json.get('items', [])  # Assuming items are submitted as a list
        print(items)
        conn = get_db_connection()
        cursor = conn.cursor()
        for item_id in items[0]:
            cursor.execute('DELETE FROM cart WHERE id = ?', (item_id,))
        invoice_number = generate_invoice_number()
        invoice_file_path = generate_invoice(invoice_number, items)
        qr_code_path =r'C:\Users\Arogya Mary\Downloads\CSE(Hons) 2nd sem\flask\static\images\Glam_Aura (1).png'
        send_confirmation_email(email, invoice_number, invoice_file_path, qr_code_path)

        return jsonify({'message': 'Confirmation sent successfully'})

    return redirect(url_for('payment'))


def send_confirmation_email(email, invoice_number, invoice_file_path, qr_code_path):
    # Email sending logic
    msg = MIMEMultipart()
    msg['From'] = 'your_email@example.com'
    msg['To'] = email
    msg['Subject'] = 'Confirmation of Purchase'

    body = f"Thank you for your purchase. Your invoice is attached below."
    msg.attach(MIMEText(body, 'plain'))

    # Attach invoice PDF
    with open(invoice_file_path, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename=invoice_{invoice_number}.pdf")
    msg.attach(part)

    # Attach QR code image
    with open(qr_code_path, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename=qr_code_{invoice_number}.jpg")
    msg.attach(part)

    # SMTP Configuration
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_username = 'rajinamary2255@gmail.com'
    smtp_password = 'hinb orca yxgf mvqu'

    # Send email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, email, msg.as_string())
        
@app.route('/payment', methods=['GET', 'POST'])
def payment():
    conn = get_db_connection()
    cart_items = conn.execute('SELECT name, price, category, quantity, details FROM cart').fetchall()
    conn.close()
    total=0
    # Convert the fetched data to a list of dictionaries
    cart_items = [dict(name=row[0], price=float(row[1]), category=row[2], quantity=int(row[3]), details=row[4]) for row in cart_items]
    for cart_item in cart_items:
        total = cart_item['price'] * cart_item['quantity']
    return render_template('payment.html', cart_items=cart_items,total=total)

if __name__ == '__main__':
    app.run(debug=True)
