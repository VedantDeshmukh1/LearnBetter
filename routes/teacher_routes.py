from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_admin import firestore
from config import db, rdb, auth
from utils import generate_video_id, validate_name
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
    
    # Fetch course details to get the course name and current video count
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
        
        # Handle file upload
        video_file = request.files['video_file']
        if video_file:
            filename = secure_filename(video_file.filename)
            file_extension = os.path.splitext(filename)[1]
            
            # Generate a unique filename for the video
            video_id = generate_video_id()
            unique_filename = f"{video_id}{file_extension}"
            
            # Save file temporarily
            temp_path = f"temp_{unique_filename}"
            video_file.save(temp_path)
            
            # Extract video duration
            video_duration = get_video_duration(temp_path)
            if video_duration is None:
                os.remove(temp_path)
                flash('Failed to process video. Please try again or use a different file.', 'error')
                return render_template('teacher/add_video.html', course_id=course_id)
            
            # Upload video to Google Drive
            video_url = upload_to_drive(temp_path, unique_filename, course_id, course_name)
            
            # Remove temporary file
            os.remove(temp_path)
            
            if not video_url:
                flash('Failed to upload video', 'error')
                return render_template('teacher/add_video.html', course_id=course_id)

            # Get the thumbnail URL
            drive_file_id = get_drive_file_id(video_url)
            thumbnail_url = f"https://drive.google.com/thumbnail?id={drive_file_id}"
        else:
            flash('No video file uploaded', 'error')
            return render_template('teacher/add_video.html', course_id=course_id)
        
        # Increment the video sequence number
        video_seq = current_video_count + 1
        
        video_data = {
            'title': video_title,
            'duration': video_duration,
            'url': video_url,
            'description': video_description,
            'thumbnail': thumbnail_url,
            'video_seq': video_seq  # Add the video sequence number
        }
        
        # Update course with new video
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
    """Extract video duration using OpenCV."""
    try:
        video = cv2.VideoCapture(file_path)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        video.release()
        return int(duration)
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