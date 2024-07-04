from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_admin import firestore
import random
import string
from config import db, rdb, auth
from utils import generate_video_id, validate_name

bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@bp.route('/login', methods=['GET', 'POST'])
def login():
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
                return redirect(url_for('teacher.dashboard'))
            else:
                flash('User not found or not a teacher', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Invalid credentials', 'error')
    return render_template('teacher/login.html')

@bp.route('/dashboard')
def dashboard():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    user_id = session['user_id']
    courses = []
    total_enrollments = 0
    total_revenue = 0
    total_ratings = 0
    total_rating_sum = 0

    course_docs = db.collection('course_details').where('course_instructor_id', '==', user_id).stream()
    for doc in course_docs:
        course = doc.to_dict()
        course['id'] = doc.id
        courses.append(course)
        
        total_enrollments += course.get('total_enrollments', 0)
        total_revenue += course.get('total_revenue', 0)
        total_ratings += course.get('total_ratings', 0)
        total_rating_sum += course.get('average_rating', 0) * course.get('total_ratings', 0)

    average_rating = total_rating_sum / total_ratings if total_ratings > 0 else 0

    analytics = {
        'total_courses': len(courses),
        'total_enrollments': total_enrollments,
        'total_revenue': total_revenue,
        'average_rating': average_rating
    }
    
    return render_template('teacher/dashboard.html', user=session['user'], courses=courses, analytics=analytics)

@bp.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    if request.method == 'POST':
        course_name = request.form['course_name']
        course_duration = int(request.form['course_duration'])
        course_price = float(request.form['course_price'])
        
        if not validate_name(course_name):
            flash('Course name must be at least 2 characters long', 'error')
            return render_template('teacher/add_course.html')
        
        course_data = {
            'course_name': course_name,
            'course_duration': course_duration,
            'course_price': course_price,
            'course_instructor': f"{session['user']['first_name']} {session['user']['last_name']}",
            'course_instructor_id': session['user_id'],
            'total_enrollments': 0,
            'total_revenue': 0,
            'average_rating': 0,
            'total_ratings': 0,
            'videos': {},
            'enrollments': {},
            'ratings': {}
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
        return redirect(url_for('teacher.dashboard'))
    
    return render_template('teacher/add_course.html')

@bp.route('/edit_course/<course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course['id'] = course_id

    if request.method == 'POST':
        course_name = request.form['course_name']
        course_duration = int(request.form['course_duration'])
        course_price = float(request.form['course_price'])
        
        course_ref.update({
            'course_name': course_name,
            'course_duration': course_duration,
            'course_price': course_price
        })
        
        flash('Course updated successfully', 'success')
        return redirect(url_for('teacher.dashboard'))
    
    return render_template('teacher/edit_course.html', course=course)

@bp.route('/view_course/<course_id>')
def view_course(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course['id'] = course_id

    return render_template('teacher/view_course.html', course=course)

@bp.route('/add_video/<course_id>', methods=['GET', 'POST'])
def add_video(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    if request.method == 'POST':
        video_title = request.form['video_title']
        video_duration = int(request.form['video_duration'])
        video_url = request.form['video_url']
        video_description = request.form['video_description']
        video_thumbnail = request.form['video_thumbnail']
        
        if not validate_name(video_title):
            flash('Video title must be at least 2 characters long', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)
        
        video_id = generate_video_id()
        
        video_data = {
            'title': video_title,
            'duration': video_duration,
            'url': video_url,
            'description': video_description,
            'thumbnail': video_thumbnail
        }
        
        # Update course with new video
        course_ref = db.collection('course_details').document(course_id)
        course_ref.update({
            f'videos.{video_id}': video_data
        })
        
        flash('Video added successfully', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))
    
    return render_template('teacher/add_video.html', course_id=course_id)

@bp.route('/edit_video/<course_id>/<video_id>', methods=['GET', 'POST'])
def edit_video(course_id, video_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    video = course['videos'][video_id]

    if request.method == 'POST':
        video_title = request.form['video_title']
        video_duration = int(request.form['video_duration'])
        video_url = request.form['video_url']
        video_description = request.form['video_description']
        video_thumbnail = request.form['video_thumbnail']
        
        if not validate_name(video_title):
            flash('Video title must be at least 2 characters long', 'error')
            return render_template('teacher/edit_video.html', course_id=course_id, video_id=video_id, video=video)
        
        course_ref.update({
            f'videos.{video_id}.title': video_title,
            f'videos.{video_id}.duration': video_duration,
            f'videos.{video_id}.url': video_url,
            f'videos.{video_id}.description': video_description,
            f'videos.{video_id}.thumbnail': video_thumbnail
        })
        
        flash('Video updated successfully', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))
    
    return render_template('teacher/edit_video.html', course_id=course_id, video_id=video_id, video=video)

@bp.route('/delete_video/<course_id>/<video_id>')
def delete_video(course_id, video_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course_ref.update({
        f'videos.{video_id}': firestore.DELETE_FIELD
    })
    
    flash('Video deleted successfully', 'success')
    return redirect(url_for('teacher.edit_course', course_id=course_id))

@bp.route('/profile')
def profile():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    user_id = session['user_id']
    user_data = db.collection('users').document(user_id).get().to_dict()
    
    return render_template('teacher/profile.html', user=user_data)

@bp.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('student.home'))
