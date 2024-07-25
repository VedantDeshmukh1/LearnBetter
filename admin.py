from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from firebase_admin import firestore
from config import db, rdb, auth, bucket
from functools import wraps
import os
import logging
from datetime import datetime, timedelta
import secrets
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Set up logging
logging.basicConfig(filename='admin.log', level=logging.INFO)

# Function to create admin user
def create_admin_user():
    admin_username = "admin"
    admin_email = "admin@example.com"
    admin_password = secrets.token_urlsafe(12)  # Generate a random password
    admin_id = str(uuid.uuid4())  # Generate a unique ID for the admin user

    # Add user to Realtime Database
    rdb.child("admin_users").child(admin_id).set({
        'username': admin_username,
        'email': admin_email,
        'password': admin_password,
        'role': 'admin'
    })

    print("Admin user created successfully!")
    print(f"Username: {admin_username}")
    print(f"Email: {admin_email}")
    print(f"Password: {admin_password}")
    print("Please save these credentials securely.")

# Create admin user when the script starts
create_admin_user()

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            admin_users = rdb.child("admin_users").get()
            admin_data = None
            for admin in admin_users.each():
                if admin.val()['username'] == username and admin.val()['password'] == password:
                    admin_data = admin.val()
                    admin_id = admin.key()
                    break
            
            if admin_data:
                session['admin'] = admin_data
                session['admin_id'] = admin_id
                flash('Admin login successful', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials', 'error')
        except Exception as e:
            print(f"Admin login error: {str(e)}")
            flash('Login error', 'error')
    return render_template('admin/login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    session.pop('admin_id', None)
    flash('Admin logged out', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@admin_required
def dashboard():
    # Fetch summary data
    users = db.collection('users').get()
    courses = db.collection('course_details').get()
    
    # User management data
    user_count = len(users)
    user_roles = {'student': 0, 'teacher': 0}
    for user in users:
        user_data = user.to_dict()
        user_roles[user_data.get('role', 'student')] += 1
    
    # Course management data
    course_count = len(courses)
    total_revenue = 0
    course_enrollments = {}
    course_revenues = {}
    
    for course in courses:
        course_data = course.to_dict()
        total_revenue += course_data.get('total_revenue', 0)
        course_enrollments[course_data['course_name']] = course_data.get('total_enrollments', 0)
        course_revenues[course_data['course_name']] = course_data.get('total_revenue', 0)
    
    # System logs
    with open('admin.log', 'r') as log_file:
        logs = log_file.readlines()[-100:]
    
    # Error console (placeholder - implement actual error fetching logic)
    errors = [
        {'timestamp': datetime.now(), 'message': 'Sample error 1'},
        {'timestamp': datetime.now() - timedelta(hours=1), 'message': 'Sample error 2'},
    ]
    
    return render_template('admin/dashboard.html', 
                           user_count=user_count,
                           course_count=course_count,
                           total_revenue=total_revenue,
                           user_roles=user_roles,
                           course_enrollments=course_enrollments,
                           course_revenues=course_revenues,
                           logs=logs,
                           errors=errors)

@app.route('/users')
@admin_required
def users():
    users = db.collection('users').get()
    return render_template('admin/users.html', users=[user.to_dict() for user in users])

@app.route('/courses')
@admin_required
def courses():
    courses = db.collection('course_details').get()
    return render_template('admin/courses.html', courses=[course.to_dict() for course in courses])

@app.route('/update_course_discount/<course_id>', methods=['POST'])
@admin_required
def update_course_discount(course_id):
    discount = request.form.get('discount', type=float)
    if discount is not None:
        db.collection('course_details').document(course_id).update({'discount': discount})
        flash('Course discount updated', 'success')
    else:
        flash('Invalid discount value', 'error')
    return redirect(url_for('courses'))

@app.route('/logs')
@admin_required
def logs():
    with open('admin.log', 'r') as log_file:
        logs = log_file.readlines()[-100:]
    return render_template('admin/logs.html', logs=logs)

@app.route('/errors')
@admin_required
def errors():
    # Placeholder - implement actual error fetching logic
    errors = [
        {'timestamp': datetime.now(), 'message': 'Sample error 1'},
        {'timestamp': datetime.now() - timedelta(hours=1), 'message': 'Sample error 2'},
    ]
    return render_template('admin/errors.html', errors=errors)

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Run on a different port than the main app
