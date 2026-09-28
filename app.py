from flask import Flask, render_template, request, redirect, url_for, session, flash
import joblib
import pandas as pd
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)

app.secret_key = "agripredict_secret_key_2026"

# ============================================================
# LOAD MODEL
# ============================================================

model = joblib.load("crop_yield_linear_model.pkl")
feature_columns = joblib.load("feature_columns.pkl")


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            reply TEXT,
            status TEXT DEFAULT 'Unread',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            replied_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    admin = conn.execute(
        "SELECT * FROM admins WHERE email = ?",
        ("admin@agripredict.com",)
    ).fetchone()

    if admin is None:

        hashed_password = generate_password_hash("Admin@123")

        conn.execute("""
            INSERT INTO admins (name, email, password)
            VALUES (?, ?, ?)
        """, (
            "AgriPredict Admin",
            "admin@agripredict.com",
            hashed_password
        ))

    conn.commit()
    conn.close()


init_db()


# ============================================================
# USER LOGIN REQUIRED
# ============================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# ADMIN REQUIRED
# ============================================================

def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "admin_id" not in session:
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return redirect(url_for("login"))


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email or not password:

            flash("Please fill all fields.", "error")

            return redirect(url_for("register"))

        conn = get_db_connection()

        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:

            conn.close()

            flash("Email already registered.", "error")

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn.execute("""
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
        """, (
            name,
            email,
            hashed_password
        ))

        conn.commit()
        conn.close()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# CROP LIST
# ============================================================

def get_crops():

    return [
        "Maize",
        "Plantains and others",
        "Potatoes",
        "Rice, paddy",
        "Sorghum",
        "Soybeans",
        "Sweet potatoes",
        "Wheat",
        "Yams"
    ]


# ============================================================
# AREA LIST
# ============================================================

def get_areas():

    areas = []

    for column in feature_columns:

        if column.startswith("Area_"):

            area_name = column.replace("Area_", "")

            areas.append(area_name)

    return sorted(areas)


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    crops = get_crops()
    areas = get_areas()

    return render_template(
        "index.html",

        # IMPORTANT:
        # Dashboard opens before prediction,
        # so this must exist.
        prediction_tonnes=None,

        crops=crops,
        areas=areas
    )


# ============================================================
# PREDICTION
# ============================================================

@app.route("/predict", methods=["POST"])
@login_required
def predict():

    try:

        area = request.form.get("area")
        item = request.form.get("item")

        year = int(request.form.get("year"))

        rainfall = float(
            request.form.get(
                "rainfall",
                request.form.get(
                    "average_rain_fall_mm_per_year",
                    0
                )
            )
        )

        pesticides = float(
            request.form.get(
                "pesticides",
                request.form.get(
                    "pesticides_tonnes",
                    0
                )
            )
        )

        temperature = float(
            request.form.get(
                "temperature",
                request.form.get(
                    "avg_temp",
                    0
                )
            )
        )

        input_data = pd.DataFrame({

            "Area": [area],

            "Item": [item],

            "Year": [year],

            "average_rain_fall_mm_per_year": [rainfall],

            "pesticides_tonnes": [pesticides],

            "avg_temp": [temperature]

        })

        input_data = pd.get_dummies(
            input_data,
            columns=[
                "Area",
                "Item"
            ],
            drop_first=True
        )

        input_data = input_data.reindex(
            columns=feature_columns,
            fill_value=0
        )

        prediction_hg_per_ha = model.predict(input_data)[0]

        prediction = prediction_hg_per_ha / 10000

        crops = get_crops()
        areas = get_areas()

        return render_template(
            "index.html",

            # IMPORTANT:
            # This is the actual prediction.
            prediction_tonnes=prediction,

            area=area,
            item=item,
            year=year,
            rainfall=rainfall,
            pesticides=pesticides,
            temperature=temperature,

            crops=crops,
            areas=areas
        )

    except Exception as e:

        flash(
            "Prediction error: " + str(e),
            "error"
        )

        return redirect(url_for("dashboard"))


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
@login_required
def about():

    return render_template("about.html")


# ============================================================
# CONTACT
# ============================================================

@app.route("/contact", methods=["GET", "POST"])
@login_required
def contact():

    if request.method == "POST":

        subject = request.form.get("subject")
        message = request.form.get("message")

        if not subject or not message:

            flash(
                "Please enter subject and message.",
                "error"
            )

            return redirect(url_for("contact"))

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO messages (
                user_id,
                subject,
                message,
                status
            )
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            subject,
            message,
            "Unread"
        ))

        conn.commit()
        conn.close()

        flash(
            "Message sent successfully.",
            "success"
        )

        return redirect(url_for("messages"))

    return render_template("contact.html")


# ============================================================
# USER MESSAGES
# ============================================================

@app.route("/messages")
@login_required
def messages():

    conn = get_db_connection()

    user_messages = conn.execute("""
        SELECT
            messages.*,
            users.name,
            users.email
        FROM messages
        JOIN users
        ON messages.user_id = users.id
        WHERE messages.user_id = ?
        ORDER BY messages.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "messages.html",
        messages=user_messages
    )


# ============================================================
# PROFILE
# ============================================================

@app.route("/profile")
@login_required
def profile():

    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if user is None:

        session.clear()

        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=user
    )


# ============================================================
# PROFILE SETTINGS
# ============================================================

@app.route("/profile/settings", methods=["GET", "POST"])
@login_required
def profile_settings():

    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user is None:

        conn.close()

        session.clear()

        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")

        if not name or not email:

            conn.close()

            flash(
                "Name and email cannot be empty.",
                "error"
            )

            return redirect(url_for("profile_settings"))

        try:

            conn.execute("""
                UPDATE users
                SET name = ?, email = ?
                WHERE id = ?
            """, (
                name,
                email,
                session["user_id"]
            ))

            conn.commit()

            session["user_name"] = name
            session["user_email"] = email

            conn.close()

            flash(
                "Profile updated successfully.",
                "success"
            )

            return redirect(url_for("profile"))

        except sqlite3.IntegrityError:

            conn.close()

            flash(
                "Email already exists.",
                "error"
            )

            return redirect(url_for("profile_settings"))

    conn.close()

    return render_template(
        "profile_settings.html",
        user=user
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()

        admin = conn.execute(
            "SELECT * FROM admins WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session.clear()

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            session["admin_email"] = admin["email"]

            return redirect(url_for("admin_dashboard"))

        flash(
            "Invalid admin email or password.",
            "error"
        )

    return render_template("admin_login.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = get_db_connection()

    total_users = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    users = conn.execute("""
        SELECT
            id,
            name,
            email,
            created_at
        FROM users
        ORDER BY created_at DESC
    """).fetchall()

    total_messages = conn.execute(
        "SELECT COUNT(*) AS count FROM messages"
    ).fetchone()["count"]

    unread_messages = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE status = 'Unread'
    """).fetchone()["count"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        users=users,
        total_messages=total_messages,
        unread_messages=unread_messages
    )


# ============================================================
# ADMIN MESSAGES
# ============================================================

@app.route("/admin/messages")
@admin_required
def admin_messages():

    conn = get_db_connection()

    all_messages = conn.execute("""
        SELECT
            messages.*,
            users.name AS user_name,
            users.email AS user_email
        FROM messages
        JOIN users
        ON messages.user_id = users.id
        ORDER BY messages.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_messages.html",
        messages=all_messages
    )


# ============================================================
# ADMIN REPLY
# ============================================================

@app.route(
    "/admin/messages/reply/<int:message_id>",
    methods=["POST"]
)
@admin_required
def admin_reply(message_id):

    reply = request.form.get("reply")

    if not reply:

        flash(
            "Reply cannot be empty.",
            "error"
        )

        return redirect(url_for("admin_messages"))

    conn = get_db_connection()

    conn.execute("""
        UPDATE messages
        SET
            reply = ?,
            status = ?,
            replied_at = ?
        WHERE id = ?
    """, (
        reply,
        "Replied",
        datetime.now(),
        message_id
    ))

    conn.commit()
    conn.close()

    flash(
        "Reply sent successfully.",
        "success"
    )

    return redirect(url_for("admin_messages"))


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)