from flask import Flask, render_template, redirect, url_for, request, session
import pyrebase
import os
import firebase_admin
from firebase_admin import credentials, firestore, db

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Firebase configuration for pyrebase
config = {
    "apiKey": "AIzaSyBWWgEmrT_RcCRcfiSSNk_mmGtmsx7JtpQ",
    "authDomain": "learnbetter-acad7.firebaseapp.com",
    "databaseURL": "https://learnbetter-acad7-default-rtdb.firebaseio.com",
    "projectId": "learnbetter-acad7",
    "storageBucket": "learnbetter-acad7.appspot.com",
    "messagingSenderId": "519730804377",
    "appId": "1:519730804377:web:ab5b8f33072ae851ba6a08",
    "measurementId": "G-RK211QSS71"
}

# Initialize pyrebase
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()

# Firebase Admin SDK initialization
cred = credentials.Certificate('learnbetter-acad7-firebase-adminsdk-36uok-bc0c7e1ebd.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://learnbetter-acad7-default-rtdb.firebaseio.com"
})

# Firestore client
firestore_db = firestore.client()

# Real-time database reference
rt_db_ref = db.reference('/')

# Routes
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        session['user'] = user['localId']
        return redirect(url_for('dashboard'))
    except Exception as e:
        error_message = 'Invalid email or password'
        if 'EMAIL_EXISTS' in str(e):
            error_message = 'Email already exists'
        return render_template('index.html', error=error_message)

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form['email']
    password = request.form['password']
    try:
        user = auth.create_user_with_email_and_password(email, password)
        session['user'] = user['localId']
        return redirect(url_for('dashboard'))
    except Exception as e:
        error_message = 'Email already exists'
        if 'WEAK_PASSWORD' in str(e):
            error_message = 'Password should be at least 6 characters'
        return render_template('index.html', error=error_message)

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template('dashboard.html')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# Route to display form to add user details
@app.route('/add_user_form')
def add_user_form():
    if 'user' in session:
        return render_template('add_user_form.html')
    return redirect(url_for('index'))

# Example of Firestore usage
@app.route('/add_user', methods=['POST'])
def add_user():
    name = request.form['name']
    age = request.form['age']
    users_ref = firestore_db.collection('users')
    users_ref.add({
        'name': name,
        'age': int(age)
    })
    return redirect(url_for('dashboard'))

# Example of Realtime Database usage
@app.route('/set_data', methods=['POST'])
def set_data():
    name = request.form['name']
    age = request.form['age']
    rt_db_ref.set({
        'name': name,
        'age': int(age)
    })
    return redirect(url_for('dashboard'))

@app.route('/teacher_signup', methods=['GET', 'POST'])
def teacher_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user_with_email_and_password(email, password)
            # Add the teacher's information to Firestore
            teachers_ref = firestore_db.collection('teachers')
            teachers_ref.document(user['localId']).set({
                'name': name,
                'email': email
            })
            session['user'] = user['localId']
            session['user_type'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        except Exception as e:
            error_message = 'Email already exists'
            if 'WEAK_PASSWORD' in str(e):
                error_message = 'Password should be at least 6 characters'
            return render_template('teacher_signup.html', error=error_message)
    return render_template('teacher_signup.html')

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'user' in session and 'user_type' in session and session['user_type'] == 'teacher':
        # Fetch the teacher's courses from Firestore
        courses_ref = firestore_db.collection('courses').where('teacher_id', '==', session['user'])
        courses = courses_ref.stream()
        return render_template('teacher_dashboard.html', courses=courses)
    return redirect(url_for('index'))

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if 'user' in session and 'user_type' in session and session['user_type'] == 'teacher':
        if request.method == 'POST':
            course_name = request.form['course_name']
            video_url = request.form['video_url']
            price = request.form['price']
            description = request.form['description']
            courses_ref = firestore_db.collection('courses')
            courses_ref.add({
                'course_name': course_name,
                'video_url': video_url,
                'price': float(price),
                'description': description,
                'teacher_id': session['user']
            })
            return redirect(url_for('teacher_dashboard'))
        return render_template('add_course.html')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
