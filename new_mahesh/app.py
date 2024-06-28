from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pyrebase
from config import firebase_config
import os
import random
import string
import re
from firebase_admin import credentials, firestore, initialize_app

app = Flask(__name__)
app.secret_key = os.urandom(24)


# Initialize Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
rdb = firebase.database()


# Initialize Firebase Admin SDK
cred = credentials.Certificate("learnbetter-acad7-firebase-adminsdk-36uok-bc0c7e1ebd.json")
initialize_app(cred)
db = firestore.client()

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
##############################################################################
#                  Student Related
##############################################################################

@app.route('/')
def home():
    courses = []
    course_docs = db.collection('course_details').limit(6).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
    return render_template('home.html', courses=courses)

@app.route('/load_more_courses/<int:offset>')
def load_more_courses(offset):
    courses = []
    course_docs = db.collection('course_details').offset(offset).limit(6).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
    return jsonify(courses)

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
            user_id = user['localId']
            
            # Add user to Realtime Database
            user_data_rdb = {
                "email": email,
                "username": username,
                "password": password,
                "first_name": first_name,
                "last_name": last_name
            }
            rdb.child("users").child(user_id).set(user_data_rdb)
            
            # Add user to Firestore
            user_data_firestore = {
                'user_id': user_id,
                'email_id': email,
                'name': f"{first_name} {last_name}",
                'role': 'student',
                'courses_enrolled': {}
            }
            db.collection('users').document(user_id).set(user_data_firestore)
            
            # Create student_details document
            student_data = {
                'student_id': user_id,
                'name': f"{first_name} {last_name}",
                'email': email,
                'purchased_courses': [],
                'progress': {}
            }
            db.collection('student_details').document(user_id).set(student_data)
            
            auth.send_email_verification(user['idToken'])
            print(f"User registered: {user_data_rdb}")  # Debug print
            flash('Registration successful. Check your email for login credentials.', 'success')
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
        
        try:
            # First, find the user in the Realtime Database to get their email
            users = rdb.child("users").get()
            user_data = None
            for user in users.each():
                if user.val()['username'] == username:
                    user_data = user.val()
                    break
            
            if user_data:
                # Use the email to sign in with Firebase Authentication
                user = auth.sign_in_with_email_and_password(user_data['email'], password)
                user_id = user['localId']
                
                session['user'] = user_data
                session['user_id'] = user_id
                flash('Login successful', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('User not found', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")  # Debug print
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

    user_id = session['user_id']
    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get()

    if student_doc.exists:
        purchased_course_ids = student_doc.to_dict().get('purchased_courses', [])
        courses = []
        for course_id in purchased_course_ids:
            course_doc = db.collection('course_details').document(course_id).get()
            if course_doc.exists:
                course = course_doc.to_dict()
                course['id'] = course_doc.id
                courses.append(course)
    else:
        courses = []

    return render_template('my_courses.html', courses=courses)

@app.route('/course/<course_id>')
def course_details(course_id):
    course_doc = db.collection('course_details').document(course_id).get()
    if course_doc.exists:
        course = course_doc.to_dict()
        course['id'] = course_doc.id
        return render_template('course_details.html', course=course)
    else:
        flash('Course not found', 'error')
        return redirect(url_for('home'))

@app.route('/my_reviews')
def my_reviews():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get()

    if student_doc.exists:
        purchased_course_ids = student_doc.to_dict().get('purchased_courses', [])
        reviews = []
        for course_id in purchased_course_ids:
            course_doc = db.collection('course_details').document(course_id).get()
            if course_doc.exists:
                course = course_doc.to_dict()
                course['id'] = course_doc.id
                reviews.append({
                    'course_id': course['id'],
                    'course_title': course['course_name'],
                    'rating': 4.5  # Replace with actual rating
                })
    else:
        reviews = []

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
        users = db.collection('users').where('email_id', '==', email).stream()
        for user in users:
            # Here you would send an email with the username and password
            flash('Password reset instructions sent to your email', 'success')
            return redirect(url_for('login'))
        flash('Email not found. Please enter the correct email or register.', 'error')
    return render_template('forgot_password.html')

@app.route('/purchase_course/<course_id>', methods=['POST'])
def purchase_course(course_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    # Add course to student_details collection
    student_ref = db.collection('student_details').document(user_id)
    student_ref.update({
        'purchased_courses': firestore.ArrayUnion([course_id])
    })

    flash('Course purchased successfully!', 'success')
    return redirect(url_for('my_courses'))

@app.route('/rate_course/<course_id>', methods=['GET', 'POST'])
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
##############################################################################
#                  Teacher Related
##############################################################################
@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        
        if len(first_name) < 2 or len(last_name) < 2:
            flash('First name and last name must be at least 2 characters long', 'error')
            return render_template('teacher_register.html')
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email address', 'error')
            return render_template('teacher_register.html')
        
        username = generate_username(first_name, last_name, email)
        password = generate_password()
        
        try:
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']
            
            # Add user to Realtime Database
            user_data_rdb = {
                "email": email,
                "username": username,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "role": "teacher"
            }
            rdb.child("users").child(user_id).set(user_data_rdb)
            
            # Add user to Firestore
            user_data_firestore = {
                'user_id': user_id,
                'email_id': email,
                'name': f"{first_name} {last_name}",
                'role': 'teacher',
                'courses': []
            }
            db.collection('users').document(user_id).set(user_data_firestore)
            
            auth.send_email_verification(user['idToken'])
            flash('Registration successful. Check your email for login credentials.', 'success')
            return redirect(url_for('teacher_login'))
        except Exception as e:
            print(f"Registration error: {str(e)}")
            flash('Registration failed', 'error')
    return render_template('teacher_register.html')

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            users = rdb.child("users").get()
            user_data = None
            for user in users.each():
                if user.val()['username'] == username and user.val()['role'] == 'teacher':
                    user_data = user.val()
                    break
            
            if user_data:
                user = auth.sign_in_with_email_and_password(user_data['email'], password)
                user_id = user['localId']
                
                session['user'] = user_data
                session['user_id'] = user_id
                flash('Login successful', 'success')
                return redirect(url_for('teacher_dashboard'))
            else:
                flash('User not found or not a teacher', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Invalid credentials', 'error')
    return render_template('teacher_login.html')

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    user_id = session['user_id']
    courses = []
    course_docs = db.collection('course_details').where('course_instructor_id', '==', user_id).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
    
    return render_template('teacher_dashboard.html', user=session['user'], courses=courses)

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    if request.method == 'POST':
        course_name = request.form['course_name']
        course_duration = int(request.form['course_duration'])
        
        course_data = {
            'course_name': course_name,
            'course_duration': course_duration,
            'course_instructor': f"{session['user']['first_name']} {session['user']['last_name']}",
            'course_instructor_id': session['user_id'],
            'videos': {}
        }
        
        # Add course to Firestore
        course_ref = db.collection('course_details').add(course_data)
        course_id = course_ref[1].id
        
        # Update user's courses in Firestore
        user_ref = db.collection('users').document(session['user_id'])
        user_ref.update({
            'courses': firestore.ArrayUnion([course_id])
        })
        
        flash('Course added successfully', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('add_course.html')

@app.route('/add_video/<course_id>', methods=['GET', 'POST'])
def add_video(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    if request.method == 'POST':
        video_title = request.form['video_title']
        video_duration = int(request.form['video_duration'])
        video_url = request.form['video_url']
        
        video_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        
        video_data = {
            'title': video_title,
            'duration': video_duration,
            'url': video_url
        }
        
        # Update course with new video
        course_ref = db.collection('course_details').document(course_id)
        course_ref.update({
            f'videos.{video_id}': video_data
        })
        
        flash('Video added successfully', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('add_video.html', course_id=course_id)

@app.route('/edit_course/<course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course['id'] = course_id

    if request.method == 'POST':
        course_name = request.form['course_name']
        course_duration = int(request.form['course_duration'])
        
        course_ref.update({
            'course_name': course_name,
            'course_duration': course_duration
        })
        
        flash('Course updated successfully', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('edit_course.html', course=course)

@app.route('/view_course/<course_id>')
def view_course(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course['id'] = course_id

    return render_template('view_course.html', course=course)

@app.route('/edit_video/<course_id>/<video_id>', methods=['GET', 'POST'])
def edit_video(course_id, video_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    video = course['videos'][video_id]

    if request.method == 'POST':
        video_title = request.form['video_title']
        video_duration = int(request.form['video_duration'])
        video_url = request.form['video_url']
        
        course_ref.update({
            f'videos.{video_id}.title': video_title,
            f'videos.{video_id}.duration': video_duration,
            f'videos.{video_id}.url': video_url
        })
        
        flash('Video updated successfully', 'success')
        return redirect(url_for('edit_course', course_id=course_id))
    
    return render_template('edit_video.html', course_id=course_id, video_id=video_id, video=video)

@app.route('/delete_video/<course_id>/<video_id>')
def delete_video(course_id, video_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher_login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course_ref.update({
        f'videos.{video_id}': firestore.DELETE_FIELD
    })
    
    flash('Video deleted successfully', 'success')
    return redirect(url_for('edit_course', course_id=course_id))


if __name__ == '__main__':
    app.run(debug=True)
