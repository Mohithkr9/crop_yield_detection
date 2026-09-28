# 🌱 AgriPredict - Crop Yield Prediction

AgriPredict is a Machine Learning based web application that predicts crop yield based on agricultural and environmental factors.

The project uses a Machine Learning model trained on a crop yield dataset and provides a simple Flask web interface for making predictions.

## 🚀 Features

- User Registration and Login
- Crop Yield Prediction
- Crop selection
- Location/Area selection
- Rainfall input
- Pesticide usage input
- Average temperature input
- Prediction displayed in tonnes per hectare
- User Profile
- Profile Settings
- Contact/Admin messaging system
- Admin Login
- Admin Dashboard
- Admin can view registered users
- Admin can reply to user messages
- Responsive web interface

## 🤖 Machine Learning

The project uses **Linear Regression** for crop yield prediction.

### Input Features

- Area
- Crop
- Year
- Average Rainfall (mm/year)
- Pesticides (tonnes)
- Average Temperature

### Target

The model predicts:

`hg/ha_yield`

The prediction is converted from hectograms per hectare to tonnes per hectare.

## 🛠️ Technologies Used

### Machine Learning
- Python
- Pandas
- NumPy
- Scikit-learn
- Linear Regression
- Joblib

### Web Development
- Flask
- HTML
- CSS
- Jinja2

### Database
- SQLite

### Development
- Google Colab
- VS Code
- Git
- GitHub

## 📁 Project Structure

```text
Crop_Yield_Prediction/
│
├── app.py
├── crop_yield_linear_model.pkl
├── feature_columns.pkl
├── users.db
├── README.md
│
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── profile_settings.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── about.html
│   ├── contact.html
│   ├── messages.html
│   └── admin_messages.html
│
└── static/
    ├── style.css
    └── background.png