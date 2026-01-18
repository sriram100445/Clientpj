import os
import uuid
from datetime import datetime
#Enter the key -------------------- need to be replaced by purchased code id and api ---------------------------

from twilio.rest import Client

TWILIO_SID = "ACxxxxxxxxxxxx"
TWILIO_TOKEN = "xxxxxxxxxxxx"
TWILIO_WHATSAPP = "whatsapp:+14155238886"
OWNER_WHATSAPP = "whatsapp:+91XXXXXXXXXX"

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)


from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ----------------- BASIC SETUP -----------------

app = Flask(__name__)
#-------------key-----------------
app.config["SECRET_KEY"] = "change_this_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///burkha_store.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# where images will be uploaded
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"


# ----------------- MODELS ----------------------


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)

    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    brand = db.Column(db.String(100), nullable=True)
    size = db.Column(db.String(50), nullable=True)   # Example: "52", "54", "S", "M"
    color = db.Column(db.String(50), nullable=True)
    price = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=False)

    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Paid")  # Paid / Pending / Shipped / Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)   # price per unit at time of order


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------- INITIAL DATA -----------------


def create_tables_and_seed():
    db.create_all()

    # Create default admin if not exists
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@example.com",
            is_admin=True
        )
        admin.set_password("admin123")   # change this after first login
        db.session.add(admin)

    # Create default categories if none
    if Category.query.count() == 0:
        default_cats = [
            ("abaya", "Abaya"),
            ("niqab", "Niqab"),
            ("imported", "Dubai Imported"),
        ]
        for slug, name in default_cats:
            db.session.add(Category(slug=slug, name=name))

    db.session.commit()


# ----------------- HELPERS -----------------
def send_whatsapp(to, message):
    twilio_client.messages.create(
        from_=TWILIO_WHATSAPP,
        to=to,
        body=message
    )

def get_cart():
    """Return cart dict from session: {product_id_str: quantity_int}"""
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart

def calculate_shipping_by_quantity(items):
    """
    items = list of cart items
    each item has quantity
    """

    total_qty = sum(item["quantity"] for item in items)

    if 1 <= total_qty <= 4:
        shipping = 50
    elif 5 <= total_qty <= 8:
        shipping = 65
    elif 9 <= total_qty <= 12:
        shipping = 100
    elif 13 <= total_qty <= 16:
        shipping = 130
    else:
        shipping = 0  # or keep 0 and handle manually

    return shipping, total_qty



def cart_items_and_total():
    cart = get_cart()
    items = []
    subtotal = 0.0

    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        if product and product.is_active:
            amount = product.price * qty
            subtotal += amount
            items.append({
                "product": product,
                "quantity": qty,
                "subtotal": amount
            })

    # Quantity-based shipping
    shipping, total_qty = calculate_shipping_by_quantity(items)

    total = subtotal + shipping

    return items, subtotal, shipping, total, total_qty




def admin_required(func):
    """Decorator for admin-only views."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            flash("Admin access only.")
            return redirect(url_for("index"))
        return func(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    # For navbar categories and cart count
    nav_categories = {c.slug: c.name for c in Category.query.order_by(Category.name).all()}
    cart = get_cart()
    cart_count = sum(cart.values())
    return dict(nav_categories=nav_categories, cart_count=cart_count, current_user=current_user)



# ----------------- PUBLIC ROUTES (SHOP) -----------------


@app.route("/")
def index():
    # Show categories + few latest products
    categories = Category.query.order_by(Category.name).all()
    latest_products = Product.query.filter_by(is_active=True).order_by(Product.id.desc()).limit(6).all()
    return render_template("index.html", categories_list=categories, latest_products=latest_products)


@app.route("/category/<slug>")
def category_page(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()

    brand = request.args.get("brand", "").strip()
    size = request.args.get("size", "").strip()
    color = request.args.get("color", "").strip()

    query = Product.query.filter_by(category_id=category.id, is_active=True)

    # filters
    if brand:
        query = query.filter_by(brand=brand)
    if size:
        query = query.filter_by(size=size)
    if color:
        query = query.filter_by(color=color)

    products = query.all()

    # For filter dropdowns
    all_products = Product.query.filter_by(category_id=category.id, is_active=True).all()
    brands = sorted({p.brand for p in all_products if p.brand})
    sizes = sorted({p.size for p in all_products if p.size})
    colors = sorted({p.color for p in all_products if p.color})

    return render_template(
        "category.html",
        category=category,
        products=products,
        brands=brands,
        sizes=sizes,
        colors=colors,
        selected_brand=brand,
        selected_size=size,
        selected_color=color
    )


@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        flash("This product is not available.")
        return redirect(request.referrer or url_for("index"))

    cart = get_cart()
    pid_str = str(product_id)
    cart[pid_str] = cart.get(pid_str, 0) + 1
    save_cart(cart)
    flash("Item added to cart.")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart")
def cart():
    items, subtotal, shipping, total, total_qty = cart_items_and_total()

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        total_qty=total_qty
    )



@app.route("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = get_cart()
    pid_str = str(product_id)
    if pid_str in cart:
        del cart[pid_str]
        save_cart(cart)
        flash("Item removed from cart.")
    return redirect(url_for("cart"))


@app.route("/checkout")
def checkout():
    items, subtotal, shipping, total, total_qty = cart_items_and_total()

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        total_qty=total_qty,
        ACCOUNT_NAME="Glamozz Boutique",
        ACCOUNT_NUMBER="123456789012",
        IFSC_CODE="HDFC0001234",
        BANK_NAME="HDFC Bank"
    )



@app.route("/payment-success", methods=["POST"])
def payment_success():
    name = request.form.get("name")
    email = request.form.get("email") or "no-email@customer.com"
    phone = request.form.get("phone")
    address = request.form.get("address")

    # 5 values
    items, subtotal, shipping, total, total_qty = cart_items_and_total()

    # SAVE ORDER
    order = Order(
        customer_name=name,
        customer_email=email,
        customer_phone=phone,
        address=address,
        total_amount=total,
        status="Pending"
    )
    db.session.add(order)
    db.session.flush()

    for item in items:
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=item["product"].id,
            product_name=item["product"].name,
            quantity=item["quantity"],
            price=item["product"].price
        ))

    db.session.commit()
    session["cart"] = {}

    # ================= WHATSAPP MESSAGE (NO EMOJIS) =================
    lines = []
    lines.append("NEW ORDER RECEIVED")
    lines.append(f"Order ID: {order.id}")
    lines.append("")
    lines.append(f"Name: {name}")
    lines.append(f"Phone: {phone}")
    lines.append(f"Email: {email}")
    lines.append(f"Address: {address}")
    lines.append("")
    lines.append("Items Ordered:")

    for item in items:
        lines.append(
            f"- {item['product'].name} x {item['quantity']} = Rs.{item['subtotal']}"
        )

    lines.append("")
    lines.append(f"Subtotal: Rs.{subtotal}")
    lines.append(f"Shipping: Rs.{shipping}")
    lines.append(f"Total Amount: Rs.{total}")
    lines.append("")
    lines.append("Please share payment screenshot to confirm order.")

    message = "\n".join(lines)

    import urllib.parse
    whatsapp_url = (
        "https://wa.me/919345508442?text=" +
        urllib.parse.quote(message)
    )

    # ✅ PASS EVERYTHING TO TEMPLATE
    return render_template(
        "payment_success.html",
        order=order,
        items=items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        whatsapp_url=whatsapp_url
    )



# ----------------- AUTH (ADMIN LOGIN) -----------------


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_admin:
            login_user(user)
            flash("Logged in as admin.")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials or not an admin.")

    return render_template("auth/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("index"))


# ----------------- ADMIN: DASHBOARD -----------------


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    product_count = Product.query.count()
    order_count = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    latest_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        order_count=order_count,
        total_revenue=total_revenue,
        latest_orders=latest_orders
    )

# ----------------- ADMIN: CATEGORIES -----------------

@app.route("/admin/categories")
@login_required
@admin_required
def admin_categories():
    categories = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/new", methods=["POST"])
@login_required
@admin_required
def admin_category_new():
    name = request.form.get("name").strip()
    slug = request.form.get("slug").strip().lower()

    if not name or not slug:
        flash("Name and slug are required.")
        return redirect(url_for("admin_categories"))

    if Category.query.filter_by(slug=slug).first():
        flash("Slug already exists.")
        return redirect(url_for("admin_categories"))

    category = Category(name=name, slug=slug)
    db.session.add(category)
    db.session.commit()

    flash("Category added successfully.")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_category_delete(category_id):
    category = Category.query.get_or_404(category_id)

    if category.products:
        flash("Cannot delete category with products.")
        return redirect(url_for("admin_categories"))

    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.")
    return redirect(url_for("admin_categories"))



# ----------------- ADMIN: PRODUCTS -----------------


@app.route("/admin/products")
@login_required
@admin_required
def admin_products():
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@login_required
@admin_required
def admin_product_new():
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        brand = request.form.get("brand")
        size = request.form.get("size")
        color = request.form.get("color")
        price = float(request.form.get("price") or 0)
        category_id = int(request.form.get("category_id"))

        image_file = request.files.get("image")
        image_filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            image_file.save(image_path)
            image_filename = unique_name

        product = Product(
            name=name,
            description=description,
            brand=brand,
            size=size,
            color=color,
            price=price,
            category_id=category_id,
            image_filename=image_filename,
            is_active=True
        )
        db.session.add(product)
        db.session.commit()
        flash("Product created.")
        return redirect(url_for("admin_products"))

    return render_template("admin/product_form.html", categories=categories, product=None)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        product.name = request.form.get("name")
        product.description = request.form.get("description")
        product.brand = request.form.get("brand")
        product.size = request.form.get("size")
        product.color = request.form.get("color")
        product.price = float(request.form.get("price") or 0)
        product.category_id = int(request.form.get("category_id"))
        product.is_active = bool(request.form.get("is_active"))

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            image_file.save(image_path)
            product.image_filename = unique_name

        db.session.commit()
        flash("Product updated.")
        return redirect(url_for("admin_products"))

    return render_template("admin/product_form.html", categories=categories, product=product)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.")
    return redirect(url_for("admin_products"))


# ----------------- ADMIN: ORDERS -----------------


@app.route("/admin/orders")
@login_required
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == "POST":
        old_status = order.status
        new_status = request.form.get("status")
        order.status = new_status
        db.session.commit()

        if old_status != "Confirmed" and new_status == "Confirmed":
            send_whatsapp(
                f"whatsapp:+91{order.customer_phone}",
                f"✅ Your order #{order.id} is confirmed.\nAmount: ₹{order.total_amount}"
            )

            send_whatsapp(
                OWNER_WHATSAPP,
                f"""🛒 NEW ORDER CONFIRMED
Name: {order.customer_name}
Phone: {order.customer_phone}
Address: {order.address}
Amount: ₹{order.total_amount}"""
            )

        flash("Order status updated.")
        return redirect(url_for("admin_orders"))

    return render_template("admin/order_detail.html", order=order)




# ----------------- MAIN -----------------


if __name__ == "__main__":
    with app.app_context():
        create_tables_and_seed()
    app.run(debug=True)
