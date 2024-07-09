from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from firebase_admin import firestore
from config import db, rdb, auth
from utils import validate_email, update_course_ratings, generate_username, generate_password
import re

bp = Blueprint('student', __name__)

@bp.route('/')
@bp.route('/home')
def home():
    print("Session data:", session)  # Debug print
    courses = []
    course_docs = db.collection('course_details').limit(6).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
    return render_template('student/home.html', courses=courses)

@bp.route('/load_more_courses/<int:offset>')
def load_more_courses(offset):
    courses = []
    course_docs = db.collection('course_details').offset(offset).limit(6).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
    return jsonify(courses)

@bp.route('/register', methods=['GET', 'POST'])
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
    return render_template('student/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            users = rdb.child("users").get()
            user_data = None
            for user in users.each():
                if user.val()['username'] == username:
                    user_data = user.val()
                    break
            
            if user_data:
                user = auth.sign_in_with_email_and_password(user_data['email'], password)
                user_id = user['localId']
                
                session['user'] = user_data
                session['user_id'] = user_id
                flash('Login successful', 'success')
                return redirect(url_for('student.home'))
            else:
                flash('User not found', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Invalid credentials', 'error')
    return render_template('student/login.html')

@bp.route('/my_courses')
def my_courses():
    if 'user' not in session:
        return redirect(url_for('student.login'))

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

    return render_template('student/my_courses.html', courses=courses)

@bp.route('/course/<course_id>')
def course_details(course_id):
    course_doc = db.collection('course_details').document(course_id).get()
    if course_doc.exists:
        course = course_doc.to_dict()
        course['id'] = course_doc.id
        if 'user' in session:
            user_id = session['user_id']
            student_doc = db.collection('student_details').document(user_id).get()
            if student_doc.exists:
                student_details = student_doc.to_dict()
            else:
                student_details = None
        else:
            student_details = None
        return render_template('student/course_details.html', course=course, student_details=student_details)
    else:
        flash('Course not found', 'error')
        return redirect(url_for('student.home'))

@bp.route('/video_player/<course_id>')
def video_player(course_id):
    if 'user' not in session:
        return redirect(url_for('student.login'))

    user_id = session['user_id']
    student_ref = db.collection('student_details').document(user_id)
    student = student_ref.get().to_dict()

    if course_id not in student.get('purchased_courses', []):
        flash('Please purchase the course to access the videos.', 'error')
        return redirect(url_for('student.course_details', course_id=course_id))

    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course['id'] = course_id

    videos = []
    for video_id, video_data in course['videos'].items():
        video_data['id'] = video_id
        videos.append(video_data)

    return render_template('student/video_player.html', course=course, videos=videos)

@bp.route('/save_video_progress', methods=['POST'])
def save_video_progress():
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    data = request.json
    video_id = data.get('video_id')
    current_time = data.get('current_time')
    course_id = data.get('course_id')

    if not all([video_id, current_time, course_id]):
        return jsonify({'error': 'Missing required data'}), 400

    student_ref = db.collection('student_details').document(user_id)
    student_ref.update({
        f'progress.{course_id}.videos.{video_id}.timestamp': current_time,
        f'progress.{course_id}.last_accessed': firestore.SERVER_TIMESTAMP
    })

    return jsonify({'success': True})

@bp.route('/student/update_video_progress/<video_id>', methods=['GET'])
def update_video_progress(video_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    course_id = request.args.get('course_id')

    if not course_id:
        return jsonify({'error': 'Missing course_id'}), 400

    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get()
    student_data = student_doc.to_dict()

    if course_id in student_data['progress'] and video_id in student_data['progress'][course_id]:
        timestamp = student_data['progress'][course_id][video_id]
        return jsonify({'timestamp': timestamp}), 200
    else:
        return jsonify({'timestamp': 0}), 200

@bp.route('/get_video_progress/<video_id>')
def get_video_progress(video_id):
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    course_id = request.args.get('course_id')

    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get().to_dict()
    timestamp = student_doc.get('progress', {}).get(course_id, {}).get('videos', {}).get(video_id, {}).get('timestamp', 0)

    return jsonify({'timestamp': timestamp})

@bp.route('/my_reviews')
def my_reviews():
    if 'user' not in session:
        return redirect(url_for('student.login'))
    
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

    return render_template('student/my_reviews.html', reviews=reviews)

@bp.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('student/profile.html', user=session['user'])

@bp.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('student.home'))

@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        if not validate_email(email):
            flash('Invalid email format', 'error')
            return render_template('student/forgot_password.html')
        
        users = db.collection('users').where('email_id', '==', email).stream()
        for user in users:
            # Here you would send an email with the username and password
            flash('Password reset instructions sent to your email', 'success')
            return redirect(url_for('student.login'))
        flash('Email not found. Please enter the correct email or register.', 'error')
    return render_template('student/forgot_password.html')

@bp.route('/purchase_course/<course_id>', methods=['POST'])
def purchase_course(course_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    # Add course to student_details collection
    student_ref = db.collection('student_details').document(user_id)
    student_ref.update({
        'purchased_courses': firestore.ArrayUnion([course_id])
    })

    # Update course details
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    
    course_ref.update({
        'total_enrollments': firestore.Increment(1),
        'total_revenue': firestore.Increment(course['course_price']),
        f'enrollments.{user_id}': {
            'enrollment_date': firestore.SERVER_TIMESTAMP,
            'progress': 0
        }
    })

    flash('Course purchased successfully!', 'success')
    return redirect(url_for('student.my_courses'))

@bp.route('/rate_course/<course_id>', methods=['GET', 'POST'])
def rate_course(course_id):
    if 'user' not in session:
        return redirect(url_for('student.login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        ratings = {
            'content_quality': int(request.form['content_quality']),
            'instructor_expertise': int(request.form['instructor_expertise']),
            'course_structure': int(request.form['course_structure']),
            'production_quality': int(request.form['production_quality']),
            'practical_examples': int(request.form['practical_examples']),
            'interactivity': int(request.form['interactivity']),
            'pace_difficulty': int(request.form['pace_difficulty']),
            'value_for_money': int(request.form['value_for_money'])
        }
        review = request.form['review']
        
        # Calculate average rating
        average_rating = sum(ratings.values()) / len(ratings)
        
        course_ref = db.collection('course_details').document(course_id)
        
        update_course_ratings(course_ref, average_rating)
        
        course_ref.update({
            f'ratings.{user_id}': {
                'rating': average_rating,
                'detailed_ratings': ratings,
                'review': review,
                'date': firestore.SERVER_TIMESTAMP
            }
        })
        flash('Thank you for rating the course!', 'success')
        return redirect(url_for('student.my_courses'))
    
    return render_template('student/rate_course.html', course_id=course_id)
