from flask import Blueprint, render_template, request, redirect, url_for, flash, session,jsonify
from firebase_admin import firestore
from config import db, rdb, auth
from utils import generate_video_id, validate_name ,generate_password,generate_username,send_email
from werkzeug.utils import secure_filename
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from utils import refresh_access_token
import json
from moviepy.editor import VideoFileClip
from PIL import Image
import io
import cv2
from PIL import Image
from googleapiclient.errors import HttpError
import regex as re
from utils import get_drive_service, upload_to_drive, get_drive_file_id

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
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        about = request.form['about']
        educational_experience = request.form['educational_experience']
        specialization = request.form['specialization']
        teaching_experience = request.form['teaching_experience']
        website = request.form['website']
        
        if len(first_name) < 2 or len(last_name) < 2:
            flash('First name and last name must be at least 2 characters long', 'error')
            return render_template('teacher/register.html')
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email address', 'error')
            return render_template('teacher/register.html')
        
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
                'role': 'teacher'
            }
            db.collection('users').document(user_id).set(user_data_firestore)
            
            # Create teacher_details document
            teacher_data = {
                'teacher_id': user_id,
                'name': f"{first_name} {last_name}",
                'email': email,
                'about': about,
                'educational_experience': educational_experience,
                'specialization': specialization,
                'teaching_experience': int(teaching_experience),
                'website': website,
                'courses_created': [],
                'total_students': 0,
                'total_revenue': 0,
                'average_rating': 0
            }
            db.collection('teacher_details').document(user_id).set(teacher_data)
            
            # Send verification email
            # Send verification email
            auth.send_email_verification(user['idToken'])
            
            # Send login credentials
            subject = "Welcome to Magpie Learning - Your Teacher Account Information"
            body = f"""
            Thank you for registering as a teacher with Magpie Learning!

            Your username is: {username}
            Your password is: {password}

            Please verify your email to activate your account.

            You can now log in and start creating courses.
            """
            send_email(email, subject, body)

            print(f"Teacher registered: {user_data_rdb}")  # Debug print
            flash('Registration successful. Check your email for login credentials and verification link.', 'success')
            return redirect(url_for('teacher.login'))
        except Exception as e:
            print(f"Registration error: {str(e)}")  # Debug print
            flash('Registration failed', 'error')
    return render_template('teacher/register.html')

##Profile
@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    user_id = session['user_id']
   
    teacher_doc_ref = db.collection('teacher_details').document(user_id)

    if request.method == 'POST':
        # Update profile
        data = request.form
        update_data = {
            'name': data.get('name'),
            'email': data.get('email'),
            'about': data.get('about'),
            'educational_experience': data.get('educational_experience'),
            'specialization': data.get('specialization'),
            'teaching_experience': int(data.get('teaching_experience', 0)),
            'website': data.get('website')
        }
        # Remove any None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        try:
            teacher_doc_ref.update(update_data)
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
        
        return redirect(url_for('teacher.profile'))

    # GET request
    try:
        teacher_doc = teacher_doc_ref.get()
        
        if not teacher_doc.exists:
            flash('Teacher profile not found. Please create a profile.', 'error')
            return render_template('teacher/profile.html', teacher=None)
        
        teacher_data = teacher_doc.to_dict()
        
        # Calculate additional statistics
        courses_ref = db.collection('course_details').where('course_instructor_id', '==', user_id)
        courses = list(courses_ref.stream())
        
        teacher_data['courses_created'] = len(courses)
        teacher_data['total_students'] = sum(course.to_dict().get('total_enrollments', 0) for course in courses)
        teacher_data['total_revenue'] = sum(course.to_dict().get('total_revenue', 0) for course in courses)
        
        # Calculate average rating
        ratings = [course.to_dict().get('average_rating', 0) for course in courses if course.to_dict().get('average_rating') is not None]
        teacher_data['average_rating'] = sum(ratings) / len(ratings) if ratings else 0
        
        # Format fields for display
        teacher_data['teaching_experience'] = f"{teacher_data.get('teaching_experience', 0)} years"
        teacher_data['total_revenue'] = f"${teacher_data['total_revenue']:.2f}"
        teacher_data['average_rating'] = f"{teacher_data['average_rating']:.1f} / 5.0"
        
        return render_template('teacher/profile.html', teacher=teacher_data)
    except Exception as e:
        flash(f'Error retrieving profile: {str(e)}', 'error')
        return render_template('teacher/profile.html', teacher=None)

@bp.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    data = request.json
    
    try:
        update_data = {
            'name': data.get('name'),
            'email': data.get('email'),
            'about': data.get('about'),
            'educational_experience': data.get('educational_experience'),
            'specialization': data.get('specialization'),
            'teaching_experience': data.get('teaching_experience'),
            'website': data.get('website')
        }
        
        # Remove any keys with None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        if update_data:
            db.collection('teacher_details').document(user_id).update(update_data)
            
            # Update the user's name in the users collection if it's provided
            if 'name' in update_data:
                db.collection('users').document(user_id).update({'name': update_data['name']})
            
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'No data provided for update'}), 400
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to update profile'}), 500

@bp.route('/public_profile/<teacher_id>')
def public_profile(teacher_id):
    teacher_doc = db.collection('teacher_details').document(teacher_id).get()
    if teacher_doc.exists:
        teacher_data = teacher_doc.to_dict()
        teacher_data['id'] = teacher_id
        courses = []
        course_docs = db.collection('course_details').where('course_instructor_id', '==', teacher_id).stream()
        for doc in course_docs:
            course = doc.to_dict()
            course['id'] = doc.id
            courses.append(course)
        return render_template('teacher/public_profile.html', teacher=teacher_data, courses=courses)
    else:
        flash('Teacher not found', 'error')
        return redirect(url_for('student.home'))

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


@bp.route('/update_video_order/<course_id>', methods=['POST'])
def update_video_order(course_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    video_order = request.json
    course_ref = db.collection('course_details').document(course_id)
    
    try:
        @firestore.transactional
        def update_transaction(transaction):
            course_snapshot = course_ref.get(transaction=transaction)
            course_data = course_snapshot.to_dict()
            videos = course_data.get('videos', {})
            
            for item in video_order:
                video_id = item['id']
                new_seq = item['seq']
                if video_id in videos:
                    videos[video_id]['video_seq'] = new_seq
            
            transaction.update(course_ref, {'videos': videos})

        # Create a transaction object
        transaction = db.transaction()
        # Execute the transaction
        update_transaction(transaction)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating video order: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    course_name = course.get('course_name', 'Unknown')
    current_video_count = len(course.get('videos', {}))
    
    if request.method == 'POST':
        video_title = request.form['video_title']
        video_description = request.form['video_description']
        
        if not validate_name(video_title):
            flash('Video title must be at least 2 characters long', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)
        
        video_file = request.files['video_file']
        if not video_file:
            flash('No video file uploaded', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)
        
        filename = secure_filename(video_file.filename)
        file_extension = os.path.splitext(filename)[1]
        video_id = generate_video_id()
        unique_filename = f"{video_id}{file_extension}"
        
        temp_path = f"temp_{unique_filename}"
        video_file.save(temp_path)
        
        video_duration = get_video_duration(temp_path)
        if video_duration is None:
            os.remove(temp_path)
            flash('Failed to process video. Please try again or use a different file.', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)
        
        video_url = upload_to_drive(temp_path, unique_filename, course_id, course_name)
        os.remove(temp_path)
        
        if not video_url:
            flash('Failed to upload video', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)

        drive_file_id = get_drive_file_id(video_url)
        thumbnail_url = f"https://drive.google.com/thumbnail?id={drive_file_id}"
        
        video_seq = current_video_count + 1
        
        video_data = {
            'title': video_title,
            'duration': video_duration,  # This is now in HH:MM:SS format
            'url': video_url,
            'description': video_description,
            'thumbnail': thumbnail_url,
            'video_seq': video_seq
        }
        
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
    course_name = course.get('course_name', 'Unknown')

    if request.method == 'POST':
        video_title = request.form['video_title']
        video_description = request.form['video_description']
        
        if not validate_name(video_title):
            flash('Video title must be at least 2 characters long', 'error')
            return render_template('teacher/edit_video.html', course_id=course_id, video_id=video_id, video=video)
        
        # Handle file upload if a new video is provided
        video_file = request.files['video_file']
        if video_file:
            filename = secure_filename(video_file.filename)
            file_extension = os.path.splitext(filename)[1]
            
            # Generate a unique filename
            unique_filename = f"{generate_video_id()}{file_extension}"
            
            # Save file temporarily
            temp_path = f"temp_{unique_filename}"
            video_file.save(temp_path)
            
            # Extract video duration
            video_duration = get_video_duration(temp_path)
            
            # Upload video to Google Drive
            video_url = upload_to_drive(temp_path, unique_filename, course_id, course_name)
            
            # Remove temporary file
            os.remove(temp_path)
            
            if not video_url:
                flash('Failed to upload video', 'error')
                return render_template('teacher/edit_video.html', course_id=course_id, video_id=video_id, video=video)
            
            # Get the new thumbnail URL
            drive_file_id = get_drive_file_id(video_url)
            thumbnail_url = f"https://drive.google.com/thumbnail?id={drive_file_id}"
            
            # Update video data
            video['url'] = video_url
            video['duration'] = video_duration
            video['thumbnail'] = thumbnail_url
        
        # Update video metadata
        video['title'] = video_title
        video['description'] = video_description
        
        # Update course with edited video
        course_ref.update({
            f'videos.{video_id}': video
        })
        
        flash('Video updated successfully', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))
    
    return render_template('teacher/edit_video.html', course_id=course_id, video_id=video_id, video=video)

def get_video_duration(file_path):
    """Extract video duration using OpenCV and return in HH:MM:SS format."""
    try:
        video = cv2.VideoCapture(file_path)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        video.release()
        
        # Convert duration to hours, minutes, seconds
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        # Format as HH:MM:SS
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception as e:
        print(f"Error getting video duration: {str(e)}")
        return None

def create_thumbnail(video_path, thumbnail_path):
    """Create thumbnail from the first frame of the video using OpenCV and save as JPEG."""
    try:
        video = cv2.VideoCapture(video_path)
        success, frame = video.read()
        if success:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            img.thumbnail((1200, 1200))  # Resize the image to a maximum of 320x320
            
            img.save(thumbnail_path, "JPEG", quality=85)
            video.release()
            return True
        else:
            print("Failed to read the first frame of the video")
            return False
    except Exception as e:
        print(f"Error creating thumbnail: {str(e)}")
        return False

@bp.route('/delete_video/<course_id>/<video_id>', methods=['POST'])
def delete_video(course_id, video_id):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('teacher.login'))
    
    course_ref = db.collection('course_details').document(course_id)
    course = course_ref.get().to_dict()
    
    if 'videos' not in course or video_id not in course['videos']:
        flash('Video not found', 'error')
        return redirect(url_for('teacher.edit_course', course_id=course_id))
    
    video = course['videos'][video_id]
    
    # Delete the video file from Google Drive
    video_url = video.get('url')
    if video_url:
        try:
            file_id = get_drive_file_id(video_url)
            if file_id:
                drive = get_drive_service()
                file = drive.CreateFile({'id': file_id})
                file.Delete()
            else:
                print(f"Could not extract file ID from URL: {video_url}")
        except Exception as e:
            print(f"Error deleting video file from Google Drive: {str(e)}")
    
    # Remove the video from the course document in Firebase
    course_ref.update({
        f'videos.{video_id}': firestore.DELETE_FIELD
    })
    
    # Reorder remaining videos
    remaining_videos = course['videos']
    del remaining_videos[video_id]
    
    # Check if video_seq exists, if not create it
    if not all('video_seq' in video for video in remaining_videos.values()):
        for i, (vid_id, vid_data) in enumerate(remaining_videos.items(), start=1):
            remaining_videos[vid_id]['video_seq'] = i
    
    # Reorder based on video_seq
    sorted_videos = sorted(remaining_videos.items(), key=lambda x: x[1]['video_seq'])
    
    # Update video_seq to ensure continuous ordering
    for i, (vid_id, vid_data) in enumerate(sorted_videos, start=1):
        remaining_videos[vid_id]['video_seq'] = i
    
    # Update the course with reordered videos
    course_ref.update({
        'videos': remaining_videos
    })
    
    flash('Video deleted successfully and remaining videos reordered', 'success')
    return redirect(url_for('teacher.edit_course', course_id=course_id))



@bp.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('student.home'))