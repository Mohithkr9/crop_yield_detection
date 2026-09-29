from flask import Flask, render_template, request, redirect, url_for, session, flash

import joblib
import pandas as pd
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import requests


# ============================================================
# FLASK APPLICATION
# ============================================================

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

    # ========================================================
    # USERS TABLE
    # ========================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ========================================================
    # ADMINS TABLE
    # ========================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ========================================================
    # MESSAGES TABLE
    # ========================================================

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


    # ========================================================
    # CREATE DEFAULT ADMIN
    # ========================================================

    admin = conn.execute(
        "SELECT * FROM admins WHERE email = ?",
        ("admin@agripredict.com",)
    ).fetchone()


    if admin is None:

        hashed_password = generate_password_hash(
            "Admin@123"
        )

        conn.execute("""
            INSERT INTO admins (
                name,
                email,
                password
            )
            VALUES (?, ?, ?)
        """, (
            "AgriPredict Admin",
            "admin@agripredict.com",
            hashed_password
        ))


    conn.commit()

    conn.close()


# Initialize database
init_db()


# ============================================================
# USER LOGIN REQUIRED
# ============================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# ADMIN REQUIRED
# ============================================================

def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "admin_id" not in session:

            return redirect(
                url_for("admin_login")
            )

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get("email")

        password = request.form.get("password")


        if not email or not password:

            flash(
                "Please enter email and password.",
                "error"
            )

            return redirect(
                url_for("login")
            )


        conn = get_db_connection()


        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()


        conn.close()


        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_email"] = user["email"]


            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid email or password.",
            "error"
        )


    return render_template(
        "login.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get("name")

        email = request.form.get("email")

        password = request.form.get("password")


        if name:

            name = name.strip()


        if email:

            email = email.strip().lower()


        if not name or not email or not password:

            flash(
                "Please fill all fields.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        conn = get_db_connection()


        try:

            existing_user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()


            if existing_user:

                flash(
                    "Email already registered.",
                    "error"
                )

                return redirect(
                    url_for("register")
                )


            hashed_password = generate_password_hash(
                password
            )


            conn.execute("""
                INSERT INTO users (
                    name,
                    email,
                    password
                )
                VALUES (?, ?, ?)
            """, (
                name,
                email,
                hashed_password
            ))


            conn.commit()


            flash(
                "Registration successful. Please login.",
                "success"
            )


            return redirect(
                url_for("login")
            )


        except sqlite3.IntegrityError as e:

            conn.rollback()

            print(
                "DATABASE INTEGRITY ERROR:",
                e
            )


            flash(
                "Email already registered.",
                "error"
            )


            return redirect(
                url_for("register")
            )


        except Exception as e:

            conn.rollback()

            print(
                "REGISTRATION ERROR:",
                e
            )


            flash(
                "Registration error: " + str(e),
                "error"
            )


            return redirect(
                url_for("register")
            )


        finally:

            conn.close()


    return render_template(
        "register.html"
    )


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

            area_name = column.replace(
                "Area_",
                ""
            )

            areas.append(
                area_name
            )


    return sorted(areas)


# ============================================================
# CROP IMPROVEMENT RECOMMENDATIONS
# ============================================================

def get_crop_improvement(
    item,
    rainfall,
    temperature,
    pesticides
):

    crop = (
        item or ""
    ).strip().lower()


    rainfall = float(
        rainfall or 0
    )


    temperature = float(
        temperature or 0
    )


    pesticides = float(
        pesticides or 0
    )


    recommendations = []


    # ========================================================
    # WATER MANAGEMENT
    # ========================================================

    if crop == "rice, paddy":

        water = (
            "Maintain adequate soil moisture throughout "
            "the crop cycle. Avoid unnecessary continuous "
            "flooding and manage irrigation according to "
            "crop stage and field condition."
        )


    elif crop in [
        "maize",
        "sorghum"
    ]:

        water = (
            "Maintain good soil moisture during germination, "
            "flowering and grain filling. Avoid prolonged "
            "waterlogging."
        )


    elif crop in [
        "potatoes",
        "sweet potatoes"
    ]:

        water = (
            "Maintain uniform soil moisture during tuber/"
            "root development. Avoid excessive irrigation "
            "because waterlogging can damage roots and "
            "increase disease risk."
        )


    elif crop == "soybeans":

        water = (
            "Maintain adequate soil moisture during "
            "establishment, flowering and pod development. "
            "Avoid prolonged waterlogging."
        )


    elif crop == "wheat":

        water = (
            "Provide irrigation according to crop growth "
            "stage and soil moisture. Avoid excessive "
            "irrigation near maturity."
        )


    elif crop in [
        "plantains and others",
        "yams"
    ]:

        water = (
            "Maintain consistent soil moisture and provide "
            "drainage during periods of heavy rainfall."
        )


    else:

        water = (
            "Maintain suitable soil moisture for the selected "
            "crop and avoid both prolonged drought stress "
            "and waterlogging."
        )


    recommendations.append({
        "icon": "💧",
        "title": "Water Management",
        "text": water
    })


    # ========================================================
    # RAINFALL MANAGEMENT
    # ========================================================

    if rainfall < 500:

        rainfall_advice = (
            "The entered annual rainfall is relatively low. "
            "Consider water-conservation practices such as "
            "mulching, suitable irrigation scheduling and "
            "moisture conservation."
        )


    elif rainfall < 1000:

        rainfall_advice = (
            "Rainfall is in a moderate range. Monitor soil "
            "moisture and provide supplemental irrigation "
            "when required by the crop."
        )


    elif rainfall < 2000:

        rainfall_advice = (
            "Rainfall is relatively high. Maintain good "
            "drainage and monitor the crop for excessive "
            "moisture and fungal disease."
        )


    else:

        rainfall_advice = (
            "The entered rainfall is very high. Prioritize "
            "field drainage, avoid prolonged waterlogging "
            "and monitor crops for diseases."
        )


    recommendations.append({
        "icon": "🌧️",
        "title": "Rainfall Management",
        "text": rainfall_advice
    })


    # ========================================================
    # TEMPERATURE MANAGEMENT
    # ========================================================

    if temperature < 15:

        temperature_advice = (
            "The entered temperature is relatively low. "
            "Monitor crop growth and avoid planting sensitive "
            "crops during unsuitable periods."
        )


    elif temperature <= 30:

        temperature_advice = (
            "The entered temperature is within a moderate "
            "range. Continue regular monitoring of crop "
            "growth and soil moisture."
        )


    else:

        temperature_advice = (
            "The entered temperature is relatively high. "
            "Use suitable irrigation, mulching and "
            "moisture-conservation practices where appropriate."
        )


    recommendations.append({
        "icon": "🌡️",
        "title": "Temperature Management",
        "text": temperature_advice
    })


    # ========================================================
    # CROP MANAGEMENT
    # ========================================================

    crop_management = {

        "maize":
            "Use suitable spacing, maintain weed control "
            "and monitor the crop particularly during "
            "vegetative growth, flowering and grain development.",


        "rice, paddy":
            "Maintain suitable field water management, "
            "control weeds and regularly inspect the crop "
            "for insects and diseases.",


        "wheat":
            "Use suitable seed quality and spacing, control "
            "weeds early and monitor the crop during important "
            "growth stages.",


        "sorghum":
            "Maintain suitable plant spacing, control weeds "
            "and monitor the crop regularly for insect and "
            "disease damage.",


        "soybeans":
            "Maintain suitable spacing, control weeds and "
            "monitor flowering and pod development carefully.",


        "potatoes":
            "Use healthy planting material, maintain suitable "
            "soil drainage and regularly monitor foliage and "
            "tubers for disease symptoms.",


        "sweet potatoes":
            "Use healthy planting material, maintain suitable "
            "soil moisture and control weeds during early "
            "crop establishment.",


        "plantains and others":
            "Maintain good drainage, remove heavily damaged "
            "plant material where appropriate and monitor "
            "leaves and bunches regularly.",


        "yams":
            "Use healthy planting material, provide suitable "
            "support where required and maintain good soil "
            "drainage."
    }


    recommendations.append({
        "icon": "🌾",
        "title": "Crop Management",
        "text": crop_management.get(
            crop,
            "Use healthy planting material, suitable spacing, "
            "proper weed management and regular crop monitoring."
        )
    })


    # ========================================================
    # SOIL MANAGEMENT
    # ========================================================

    recommendations.append({

        "icon": "🌱",

        "title": "Soil Management",

        "text": (
            "Use soil-test-based fertilizer recommendations. "
            "Maintain soil organic matter and avoid applying "
            "nutrients excessively. Good drainage and appropriate "
            "soil structure are important for healthy crop growth."
        )

    })


    # ========================================================
    # PEST MANAGEMENT
    # ========================================================

    recommendations.append({

        "icon": "🐛",

        "title": "Pest Management",

        "text": (
            "Inspect the crop regularly for insects, disease "
            "symptoms and weed problems. Identify the pest or "
            "disease before selecting any pesticide. Prefer "
            "integrated pest management practices and use "
            "chemicals only when necessary."
        )

    })


    # ========================================================
    # PESTICIDE GUIDANCE
    # ========================================================

    if pesticides <= 0:

        pesticide_status = (
            "No pesticide quantity was entered for the prediction."
        )


    else:

        pesticide_status = (

            f"The prediction input contains "
            f"{pesticides:g} tonnes of pesticide. "

            "This value is a model input and should NOT be "
            "treated as the recommended field application rate."

        )


    recommendations.append({

        "icon": "🧪",

        "title": "Pesticide Guidance",

        "text": pesticide_status

    })


    # ========================================================
    # CROP MONITORING
    # ========================================================

    recommendations.append({

        "icon": "📊",

        "title": "Crop Monitoring",

        "text": (
            "Monitor rainfall, temperature, soil moisture, "
            "crop growth, pest activity and disease symptoms "
            "throughout the growing season. Record observations "
            "so that future management decisions can be improved."
        )

    })


    return recommendations


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

        prediction_tonnes=None,

        crops=crops,

        areas=areas

    )


# ============================================================
# PREDICTION
# ============================================================

@app.route(
    "/predict",
    methods=["POST"]
)
@login_required
def predict():

    try:

        # ====================================================
        # GET FORM DATA
        # ====================================================

        area = request.form.get(
            "area"
        )


        item = request.form.get(
            "item"
        )


        year = int(
            request.form.get(
                "year"
            )
        )


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


        # ====================================================
        # CREATE INPUT DATAFRAME
        # ====================================================

        input_data = pd.DataFrame({

            "Area": [area],

            "Item": [item],

            "Year": [year],

            "average_rain_fall_mm_per_year": [
                rainfall
            ],

            "pesticides_tonnes": [
                pesticides
            ],

            "avg_temp": [
                temperature
            ]

        })


        # ====================================================
        # CONVERT CATEGORICAL VALUES
        # ====================================================

        input_data = pd.get_dummies(

            input_data,

            columns=[
                "Area",
                "Item"
            ],

            drop_first=True

        )


        # ====================================================
        # MATCH TRAINED MODEL COLUMNS
        # ====================================================

        input_data = input_data.reindex(

            columns=feature_columns,

            fill_value=0

        )


        # ====================================================
        # MODEL PREDICTION
        # ====================================================

        prediction_hg_per_ha = model.predict(
            input_data
        )[0]


        # ====================================================
        # CONVERT hg/ha TO tonnes/ha
        # ====================================================

        prediction = (
            prediction_hg_per_ha / 10000
        )


        # ====================================================
        # GET DROPDOWN DATA
        # ====================================================

        crops = get_crops()

        areas = get_areas()


        # ====================================================
        # CROP IMPROVEMENT RECOMMENDATIONS
        # ====================================================

        crop_recommendations = get_crop_improvement(

            item,

            rainfall,

            temperature,

            pesticides

        )


        # ====================================================
        # DISPLAY RESULT
        # ====================================================

        return render_template(

            "index.html",

            prediction_tonnes=prediction,

            area=area,

            item=item,

            year=year,

            rainfall=rainfall,

            pesticides=pesticides,

            temperature=temperature,

            crops=crops,

            areas=areas,

            crop_recommendations=crop_recommendations

        )


    except Exception as e:

        print(
            "PREDICTION ERROR:",
            e
        )


        flash(

            "Prediction error: " + str(e),

            "error"

        )


        return redirect(
            url_for("dashboard")
        )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
@login_required
def about():

    return render_template(
        "about.html"
    )


# ============================================================
# CONTACT
# ============================================================

@app.route(
    "/contact",
    methods=["GET", "POST"]
)
@login_required
def contact():

    if request.method == "POST":

        subject = request.form.get(
            "subject"
        )


        message = request.form.get(
            "message"
        )


        if not subject or not message:

            flash(
                "Please enter subject and message.",
                "error"
            )


            return redirect(
                url_for("contact")
            )


        conn = get_db_connection()


        try:

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


            flash(
                "Message sent successfully.",
                "success"
            )


        except Exception as e:

            conn.rollback()


            print(
                "CONTACT ERROR:",
                e
            )


            flash(
                "Could not send message.",
                "error"
            )


        finally:

            conn.close()


        return redirect(
            url_for("messages")
        )


    return render_template(
        "contact.html"
    )


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

        return redirect(
            url_for("login")
        )


    return render_template(

        "profile.html",

        user=user

    )


# ============================================================
# PROFILE SETTINGS
# ============================================================

@app.route(
    "/profile/settings",
    methods=["GET", "POST"]
)
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

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        name = request.form.get(
            "name"
        )


        email = request.form.get(
            "email"
        )


        if name:

            name = name.strip()


        if email:

            email = email.strip().lower()


        if not name or not email:

            conn.close()


            flash(
                "Name and email cannot be empty.",
                "error"
            )


            return redirect(
                url_for("profile_settings")
            )


        try:

            conn.execute("""

                UPDATE users

                SET

                    name = ?,

                    email = ?

                WHERE id = ?

            """, (

                name,

                email,

                session["user_id"]

            ))


            conn.commit()


            session["user_name"] = name

            session["user_email"] = email


            flash(
                "Profile updated successfully.",
                "success"
            )


            return redirect(
                url_for("profile")
            )


        except sqlite3.IntegrityError:

            conn.rollback()


            flash(
                "Email already exists.",
                "error"
            )


            return redirect(
                url_for("profile_settings")
            )


        except Exception as e:

            conn.rollback()


            print(
                "PROFILE UPDATE ERROR:",
                e
            )


            flash(
                "Profile update failed.",
                "error"
            )


            return redirect(
                url_for("profile_settings")
            )


        finally:

            conn.close()


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


    return redirect(
        url_for("login")
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        email = request.form.get(
            "email"
        )


        password = request.form.get(
            "password"
        )


        if not email or not password:

            flash(
                "Please enter email and password.",
                "error"
            )


            return redirect(
                url_for("admin_login")
            )


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


            return redirect(
                url_for("admin_dashboard")
            )


        flash(
            "Invalid admin email or password.",
            "error"
        )


    return render_template(
        "admin_login.html"
    )


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

    reply = request.form.get(
        "reply"
    )


    if not reply:

        flash(
            "Reply cannot be empty.",
            "error"
        )


        return redirect(
            url_for("admin_messages")
        )


    conn = get_db_connection()


    try:

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


        flash(
            "Reply sent successfully.",
            "success"
        )


    except Exception as e:

        conn.rollback()


        print(
            "ADMIN REPLY ERROR:",
            e
        )


        flash(
            "Could not send reply.",
            "error"
        )


    finally:

        conn.close()


    return redirect(
        url_for("admin_messages")
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()


    return redirect(
        url_for("admin_login")
    )


# ============================================================
# WEATHER
# ============================================================

@app.route("/weather")
@login_required
def weather():

    # Configured weather location.
    # This is NOT the user's precise GPS location.

    latitude = 12.9716

    longitude = 77.5946


    try:

        response = requests.get(

            "https://api.open-meteo.com/v1/forecast",

            params={

                "latitude": latitude,

                "longitude": longitude,

                "current":
                    "temperature_2m,relative_humidity_2m,precipitation",

                "timezone": "auto"

            },

            timeout=10

        )


        response.raise_for_status()


        data = response.json()


        current = data.get(
            "current",
            {}
        )


        return {

            "temperature":
                current.get(
                    "temperature_2m"
                ),

            "humidity":
                current.get(
                    "relative_humidity_2m"
                ),

            "rainfall":
                current.get(
                    "precipitation"
                ),

            "latitude":
                latitude,

            "longitude":
                longitude

        }


    except Exception as e:

        print(
            "WEATHER ERROR:",
            e
        )


        return {

            "error":
                "Weather service unavailable"

        }, 503


# ============================================================
# AVERAGE ANNUAL RAINFALL
# ============================================================

@app.route("/average-rainfall")
@login_required
def average_rainfall():

    latitude = 12.9716

    longitude = 77.5946


    start_year = 2016

    end_year = 2025


    start_date = "2016-01-01"

    end_date = "2025-12-31"


    try:

        response = requests.get(

            "https://archive-api.open-meteo.com/v1/archive",

            params={

                "latitude": latitude,

                "longitude": longitude,

                "start_date": start_date,

                "end_date": end_date,

                "daily": "precipitation_sum",

                "timezone": "auto"

            },

            timeout=20

        )


        response.raise_for_status()


        data = response.json()


        dates = data.get(
            "daily",
            {}
        ).get(
            "time",
            []
        )


        rainfall_values = data.get(
            "daily",
            {}
        ).get(
            "precipitation_sum",
            []
        )


        yearly_totals = {}


        for date_string, value in zip(
            dates,
            rainfall_values
        ):

            if value is None:

                continue


            year = date_string[:4]


            yearly_totals.setdefault(
                year,
                0.0
            )


            yearly_totals[year] += float(
                value
            )


        if not yearly_totals:

            raise ValueError(
                "No historical rainfall data returned"
            )


        average = (
            sum(yearly_totals.values())
            /
            len(yearly_totals)
        )


        actual_start_year = min(
            int(year)
            for year in yearly_totals.keys()
        )


        actual_end_year = max(
            int(year)
            for year in yearly_totals.keys()
        )


        return {

            "average_rainfall":
                round(
                    average,
                    2
                ),

            "start_year":
                actual_start_year,

            "end_year":
                actual_end_year,

            "years_used":
                len(yearly_totals),

            "years":
                f"{actual_start_year}–{actual_end_year}",

            "yearly_values":
                yearly_totals,

            "latitude":
                latitude,

            "longitude":
                longitude

        }


    except Exception as e:

        print(
            "AVERAGE RAINFALL ERROR:",
            e
        )


        return {

            "error":
                "Historical rainfall service unavailable"

        }, 503


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )