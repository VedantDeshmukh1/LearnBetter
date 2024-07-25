from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from firebase_admin import firestore
from config import db, rdb, auth
from utils import validate_email, update_course_ratings, generate_username, generate_password, send_email
import re
import requests
from datetime import datetime, timedelta

bp = Blueprint('student', __name__)

@bp.route('/')
@bp.route('/home')
def home():
    print("Session data:", session)  # Debug print
    courses = []
    course_docs = db.collection('course_details').order_by('total_enrollments', direction=firestore.Query.DESCENDING).limit(8).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        
        # Get the thumbnail of the first video by sequence
        sorted_videos = sorted(course['videos'].values(), key=lambda x: x['video_seq'])
        first_video = sorted_videos[0] if sorted_videos else None
        course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
        
        # Calculate average rating and total ratings
        ratings = course.get('ratings', {})
        if ratings:
            course['average_rating'] = sum(r['rating'] for r in ratings.values()) / len(ratings)
            course['total_ratings'] = len(ratings)
        else:
            course['average_rating'] = None
            course['total_ratings'] = 0
        
        courses.append(course)
    
    show_more_button = len(courses) == 8
    
    user_courses = []
    purchased_course_ids = []
    if 'user' in session:
        user_id = session['user_id']
        student_ref = db.collection('student_details').document(user_id)
        student_doc = student_ref.get()
        if student_doc.exists:
            student_data = student_doc.to_dict()
            purchased_course_ids = student_data.get('purchased_courses', [])
            progress = student_data.get('progress', {})
            
            for course_id in purchased_course_ids:
                course_doc = db.collection('course_details').document(course_id).get()
                if course_doc.exists:
                    course = course_doc.to_dict()
                    course['id'] = course_doc.id
                    
                    # Get the thumbnail of the first video by sequence
                    sorted_videos = sorted(course['videos'].values(), key=lambda x: x['video_seq'])
                    first_video = sorted_videos[0] if sorted_videos else None
                    course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
                    
                    course['progress'] = progress.get(course_id, {}).get('overall_progress', 0)
                    user_courses.append(course)
            
            courses = [course for course in courses if course['id'] not in purchased_course_ids]
    
    show_popular_courses = len(courses) > 0
    
    return render_template('student/home.html', courses=courses, user_courses=user_courses, show_more_button=show_more_button, show_popular_courses=show_popular_courses)

@bp.route('/get_user_courses')
def get_user_courses():
    if 'user' not in session:
        return jsonify([])
    
    user_id = session['user_id']
    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get()
    
    if student_doc.exists:
        purchased_course_ids = student_doc.to_dict().get('purchased_courses', [])
        progress = student_doc.to_dict().get('progress', {})
        user_courses = []
        for course_id in purchased_course_ids:
            course_doc = db.collection('course_details').document(course_id).get()
            if course_doc.exists:
                course = course_doc.to_dict()
                course['id'] = course_doc.id
                course['progress'] = progress.get(course_id, {}).get('overall_progress', 0)
                
                # Get the thumbnail of the first video by sequence
                sorted_videos = sorted(course['videos'].values(), key=lambda x: x['video_seq'])
                first_video = sorted_videos[0] if sorted_videos else None
                course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
                
                user_courses.append(course)
        return jsonify(user_courses)
    else:
        return jsonify([])

@bp.route('/load_more_courses/<int:offset>')
def load_more_courses(offset):
    courses = []
    course_docs = db.collection('course_details').order_by('total_enrollments', direction=firestore.Query.DESCENDING).offset(offset).limit(8).stream()
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
            
            # Send verification email
            auth.send_email_verification(user['idToken'])
            
            # Send login credentials
            subject = "Welcome to Magpie Learning - Your Account Information"
            body = f"Thank you for registering with Magpie Learning!\n\nYour username is: {username}\nYour password is: {password}\n\nPlease verify your email to activate your account."
            send_email(email, subject, body)

            print(f"User registered: {user_data_rdb}")  # Debug print
            flash('Registration successful. Check your email for login credentials and verification link.', 'success')
            return redirect(url_for('student.login'))
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
        
        # Sort videos by sequence
        sorted_videos = sorted(course['videos'].values(), key=lambda x: x['video_seq'])
        course['sorted_videos'] = sorted_videos
        
        # Get the thumbnail of the first video
        first_video = next((v for v in sorted_videos if v['video_seq'] == 1), None)
        course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
        
        # Calculate average rating and total ratings
        ratings = course.get('ratings', {})
        if ratings:
            course['average_rating'] = sum(r['rating'] for r in ratings.values()) / len(ratings)
            course['total_ratings'] = len(ratings)
        else:
            course['average_rating'] = None
            course['total_ratings'] = 0
        
        # Get reviews
        course['reviews'] = []
        for student_id, rating_data in ratings.items():
            if 'review' in rating_data:
                student_doc = db.collection('student_details').document(student_id).get()
                student_name = student_doc.to_dict()['name'] if student_doc.exists else 'Anonymous'
                course['reviews'].append({
                    'student_name': student_name,
                    'rating': rating_data['rating'],
                    'comment': rating_data['review']
                })
        
        # Get related courses (people also purchased)
        related_courses = []
        related_course_docs = db.collection('course_details').order_by('total_enrollments', direction=firestore.Query.DESCENDING).limit(5).stream()
        for doc in related_course_docs:
            if doc.id != course_id:
                related_course = doc.to_dict()
                related_course['id'] = doc.id
                # Get the thumbnail of the first video
                first_video = next((v for v in related_course['videos'].values() if v['video_seq'] == 1), None)
                related_course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
                related_courses.append(related_course)
        
        if 'user' in session:
            user_id = session['user_id']
            student_doc = db.collection('student_details').document(user_id).get()
            if student_doc.exists:
                student_details = student_doc.to_dict()
            else:
                student_details = None
        else:
            student_details = None
        
        return render_template('student/course_details.html', course=course, student_details=student_details, related_courses=related_courses)
    else:
        flash('Course not found', 'error')
        return redirect(url_for('student.home'))

@bp.route('/search_courses')
def search_courses():
    query = request.args.get('query', '').lower()
    courses = []
    course_docs = db.collection('course_details').stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        if query in course['course_name'].lower() or query in course['course_instructor'].lower():
            # Get the thumbnail of the first video
            first_video = next((v for v in course['videos'].values() if v['video_seq'] == 1), None)
            course['thumbnail'] = first_video['thumbnail'] if first_video else url_for('static', filename='images/default_thumbnail.jpg')
            
            # Calculate average rating and total ratings
            ratings = course.get('ratings', {})
            if ratings:
                course['average_rating'] = sum(r['rating'] for r in ratings.values()) / len(ratings)
                course['total_ratings'] = len(ratings)
            else:
                course['average_rating'] = None
                course['total_ratings'] = 0
            
            courses.append(course)
    return jsonify(courses)

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
    progress_data = student.get('progress', {}).get(course_id, {})
    videos_completed = progress_data.get('videos_completed', {})
    
    for video_id, video_data in course['videos'].items():
        video_data['id'] = video_id
        video_data['description'] = video_data.get('description', 'No description available.')
        video_data['duration'] = video_data.get('duration', 'Duration not available')
        video_data['date'] = video_data.get('date', 'Date not available')
        video_data['completed'] = videos_completed.get(video_id, False)
        videos.append(video_data)

    # Sort videos by sequence
    videos.sort(key=lambda x: x['video_seq'])

    overall_progress = progress_data.get('overall_progress', 0)

    return render_template('student/video_player.html', course=course, videos=videos, progress_data=progress_data, overall_progress=overall_progress)

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
        
        users = rdb.child("users").get()
        user_data = None
        for user in users.each():
            if user.val()['email'] == email:
                user_data = user.val()
                break
        
        if user_data:
            subject = "Your Magpie Learning Account Information"
            body = f"Your username is: {user_data['username']}\nYour password is: {user_data['password']}"
            if send_email(email, subject, body):
                flash('Your login credentials have been sent to your email', 'success')
                return redirect(url_for('student.login'))
            else:
                flash('An error occurred while sending the email. Please try again later.', 'error')
        else:
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

    # Initialize progress tracking
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    
    progress_data = {
        'user_id': user_id,
        'course_id': course_id,
        'lessons_completed': {},
        'overall_progress': 0,
        'last_accessed': firestore.SERVER_TIMESTAMP
    }
    
    for lesson_id in course.get('lessons', {}):
        progress_data['lessons_completed'][lesson_id] = False
    
    #db.collection('student_progress').add(progress_data)

    # Update user document in Firestore
    user_ref = db.collection('users').document(user_id)
    user_ref.update({
        f'courses_enrolled.{course_id}': firestore.SERVER_TIMESTAMP
    })

    # Update course details
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

@bp.route('/update_progress/<course_id>/<video_id>', methods=['POST'])
def update_progress(course_id, video_id):
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    data = request.json
    progress = data['progress']
    
    student_ref = db.collection('student_details').document(user_id)
    student_doc = student_ref.get()
    
    if not student_doc.exists:
        return jsonify({'error': 'Student data not found'}), 404
    
    student_data = student_doc.to_dict()
    
    if 'progress' not in student_data:
        student_data['progress'] = {}
    if course_id not in student_data['progress']:
        student_data['progress'][course_id] = {'overall_progress': 0, 'videos_completed': {}}
    
    # Update the completed status of the video
    student_data['progress'][course_id]['videos_completed'][video_id] = True
    
    # Update overall progress
    student_data['progress'][course_id]['overall_progress'] = round(progress, 2)
    
    student_ref.update(student_data)
    
    return jsonify({'success': True, 'progress': student_data['progress'][course_id]['overall_progress']})

@bp.route('/save_video_progress', methods=['POST'])
def save_video_progress():
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    data = request.json
    video_id = data['video_id']
    current_time = data['current_time']
    course_id = data['course_id']

    # We'll store this information in memory or a separate database
    # Instead of Firestore, for example:
    video_progress[user_id] = video_progress.get(user_id, {})
    video_progress[user_id][course_id] = video_progress[user_id].get(course_id, {})
    video_progress[user_id][course_id][video_id] = current_time

    return jsonify({'success': True})

# Add this at the top of your file
video_progress = {}

@bp.route('/get_video_progress/<video_id>')
def get_video_progress(video_id):
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    course_id = request.args.get('course_id')

    timestamp = video_progress.get(user_id, {}).get(course_id, {}).get(video_id, 0)
    return jsonify({'timestamp': timestamp})

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

# Add this function outside of any route
def calculate_average_rating(user_id):
    # Fetch all courses rated by the user
    courses = db.collection('course_details').where(f'ratings.{user_id}', '!=', None).get()
    total_rating = sum(course.to_dict()['ratings'][user_id]['rating'] for course in courses)
    return total_rating / len(courses) if courses else 0

def calculate_average_rating(user_id):
    # Fetch all courses
    courses = db.collection('course_details').stream()
    total_rating = 0
    rated_courses = 0
    
    for course in courses:
        course_data = course.to_dict()
        if 'ratings' in course_data and user_id in course_data['ratings']:
            total_rating += course_data['ratings'][user_id]['rating']
            rated_courses += 1
    
    return total_rating / rated_courses if rated_courses > 0 else 0

@bp.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('student.login'))

    user_id = session['user_id']
    user = session['user']

    try:
        # Fetch student details and course data
        student_ref = db.collection('student_details').document(user_id)
        student_doc = student_ref.get()
        if not student_doc.exists:
            flash('Student data not found', 'error')
            return redirect(url_for('student.home'))
        
        student_data = student_doc.to_dict()

        # Update the analytics data in the dashboard route
        analytics = {
            'total_courses': len(student_data.get('purchased_courses', [])),
            'completed_courses': 0,
            'total_learning_hours': 0,
            'average_rating': calculate_average_rating(user_id)
        }

        progress_data = student_data.get('progress', {})
        if isinstance(progress_data, dict):
            analytics['completed_courses'] = sum(1 for course in progress_data.values() if isinstance(course, dict) and course.get('overall_progress', 0) == 100)
            analytics['total_learning_hours'] = sum(
                sum(video.get('duration', 0) for video in course.get('videos', {}).values() if isinstance(video, dict) and video.get('completed', False))
                for course in progress_data.values() if isinstance(course, dict)
            ) / 3600  # Convert seconds to hours

        # Prepare chart data based on video completion
        chart_data = {
            'labels': [],
            'data': []
        }
        for i in range(7):  # Last 7 days
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_data['labels'].append(date)
            if isinstance(progress_data, dict):
                chart_data['data'].append(sum(
                    1 for course in progress_data.values() if isinstance(course, dict)
                    for video in course.get('videos_completed', {}).values() if isinstance(video, dict)
                    and video.get('completion_date', '').startswith(date)
                ))
            else:
                chart_data['data'].append(0)
        chart_data['labels'].reverse()
        chart_data['data'].reverse()

        # Fetch recent activities from the student_details collection
        recent_activities = student_data.get('recent_activities', [])[:5]  # Get the last 5 activities

        # Fetch course details
        courses = []
        for course_id in student_data.get('purchased_courses', []):
            course_doc = db.collection('course_details').document(course_id).get()
            if course_doc.exists:
                course = course_doc.to_dict()
                course['id'] = course_doc.id
                course['progress'] = progress_data.get(course_id, {}).get('overall_progress', 0) if isinstance(progress_data, dict) else 0
                courses.append(course)

        return render_template('student/dashboard.html', 
                               user=user, 
                               analytics=analytics, 
                               courses=courses, 
                               chart_data=chart_data, 
                               recent_activities=recent_activities)
    
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        flash('An error occurred while loading the dashboard', 'error')
        return redirect(url_for('student.home'))

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