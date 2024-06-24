from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyrebase
from config import firebase_config
import os
import random
import string
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()

def generate_username(first_name, last_name, email):
    username = first_name[:2] + last_name[:2] + str(len(email)) + str(random.randint(100, 999))
    return username

def generate_password():
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '@#$&_^%'
    
    password = ''.join(random.choice(lowercase) for _ in range(3))
    password += ''.join(random.choice(uppercase) for _ in range(3))
    password += ''.join(random.choice(digits) for _ in range(2))
    password += ''.join(random.choice(special) for _ in range(2))
    
    password_list = list(password)
    random.shuffle(password_list)
    return ''.join(password_list)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        
        if len(first_name) < 2 or len(last_name) < 2:
            flash('First name and last name must be at least 2 characters long', 'error')
            return render_template('register.html')
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email address', 'error')
            return render_template('register.html')
        
        username = generate_username(first_name, last_name, email)
        password = generate_password()
        
        try:
            user = auth.create_user_with_email_and_password(email, password)
            # Add user to database
            user_data = {
                "email": email,
                "username": username,
                "password": password,
                "first_name": first_name,
                "last_name": last_name
            }
            db.child("users").push(user_data)
            print(f"User registered: {user_data}")  # Debug print
            flash('Registration successful. Check your email for login credentials.', 'success')
            # Here you would send an email with the username and password
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Registration error: {str(e)}")  # Debug print
            flash('Registration failed', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = db.child("users").get()
        if users.each() is None:
            print("No users found in the database")
            flash('No users found in the database', 'error')
            return render_template('login.html')

        for user in users.each():
            print(f"Checking user: {user.val()}")  # Debug print
            if 'email' in user.val() and user.val()['email'] == username and user.val()['password'] == password:
                session['user'] = user.val()
                flash('Login successful', 'success')
                return redirect(url_for('dashboard'))
            elif 'username' in user.val() and user.val()['username'] == username and user.val()['password'] == password:
                session['user'] = user.val()
                flash('Login successful', 'success')
                return redirect(url_for('dashboard'))
        
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/my_courses')
def my_courses():
    if 'user' not in session:
        return redirect(url_for('login'))
    # Fetch user's courses from the database
    # For now, we'll use dummy data
    courses = [
        {"id": 1, "title": "Python Basics", "summary": "Learn Python fundamentals"},
        {"id": 2, "title": "Web Development", "summary": "Build responsive websites"}
    ]
    return render_template('my_courses.html', courses=courses)

@app.route('/browse_courses')
def browse_courses():
    # Fetch all courses from the database
    # For now, we'll use dummy data
    courses = [
        {"id": 1, "title": "Python Basics", "summary": "Learn Python fundamentals", "sample_videos": ["intro.mp4", "variables.mp4"]},
        {"id": 2, "title": "Web Development", "summary": "Build responsive websites", "sample_videos": ["html_basics.mp4", "css_intro.mp4"]},
        {"id": 3, "title": "Data Science", "summary": "Analyze and visualize data", "sample_videos": ["pandas_intro.mp4", "matplotlib_basics.mp4"]}
    ]
    return render_template('browse_courses.html', courses=courses)

@app.route('/my_reviews')
def my_reviews():
    if 'user' not in session:
        return redirect(url_for('login'))
    # Fetch user's reviews from the database
    # For now, we'll use dummy data
    reviews = [
        {"course_id": 1, "course_title": "Python Basics", "rating": 4.5},
        {"course_id": 2, "course_title": "Web Development", "rating": 5}
    ]
    return render_template('my_reviews.html', reviews=reviews)

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html', user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('home'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        users = db.child("users").get()
        for user in users.each():
            if user.val()['email'] == email:
                # Here you would send an email with the username and password
                flash('Password reset instructions sent to your email', 'success')
                return redirect(url_for('login'))
        flash('Email not found. Please enter the correct email or register.', 'error')
    return render_template('forgot_password.html')

@app.route('/rate_course/<int:course_id>', methods=['GET', 'POST'])
def rate_course(course_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        rating = {
            "content_quality": int(request.form['content_quality']),
            "instructor_expertise": int(request.form['instructor_expertise']),
            "course_structure": int(request.form['course_structure']),
            "production_quality": int(request.form['production_quality']),
            "practical_examples": int(request.form['practical_examples']),
            "interactivity": int(request.form['interactivity']),
            "pace_difficulty": int(request.form['pace_difficulty']),
            "value_for_money": int(request.form['value_for_money'])
        }
        # Here you would save the rating to the database
        flash('Thank you for rating the course!', 'success')
        return redirect(url_for('my_courses'))
    return render_template('rate_course.html', course_id=course_id)

if __name__ == '__main__':
    app.run(debug=True)