from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyrebase
from config import firebase_config
import os
import random
import string
import re
from firebase_admin import credentials, firestore, initialize_app

# Initialize Firebase Admin SDK
cred = credentials.Certificate("learnbetter-acad7-firebase-adminsdk-36uok-bc0c7e1ebd.json")
initialize_app(cred)
db = firestore.client()

# Sample data for course_details collection
course_details_data = [
    {
        'course_id': 'python101',
        'course_instructor': 'John Doe',
        'course_name': 'Python Basics',
        'course_instructor_id': 'john_doe_123',
        'course_duration': 20,
        'videos': {
            'video1': {
                'title': 'Introduction to Python',
                'duration': 15,
                'url': 'https://example.com/python_intro.mp4'
            },
            'video2': {
                'title': 'Variables and Data Types',
                'duration': 20,
                'url': 'https://example.com/python_variables.mp4'
            }
        }
    },
    {
        'course_id': 'webdev101',
        'course_instructor': 'Jane Smith',
        'course_name': 'Web Development Fundamentals',
        'course_instructor_id': 'jane_smith_456',
        'course_duration': 30,
        'videos': {
            'video1': {
                'title': 'HTML Basics',
                'duration': 25,
                'url': 'https://example.com/html_basics.mp4'
            },
            'video2': {
                'title': 'CSS Styling',
                'duration': 30,
                'url': 'https://example.com/css_styling.mp4'
            }
        }
    }
]

# Sample data for users collection
users_data = [
    {
        'user_id': 'user123',
        'email_id': 'student@example.com',
        'name': 'Student One',
        'role': 'student',
        'courses_enrolled': {
            'python101': firestore.SERVER_TIMESTAMP,
            'webdev101': firestore.SERVER_TIMESTAMP
        }
    },
    {
        'user_id': 'user456',
        'email_id': 'teacher@example.com',
        'name': 'Teacher One',
        'role': 'teacher',
        'courses_enrolled': {}
    }
]

# Sample data for student_details collection
student_details_data = [
    {
        'student_id': 'user123',
        'name': 'Student One',
        'email': 'student@example.com',
        'purchased_courses': ['python101', 'webdev101'],
        'progress': {
            'python101': {
                'completion_percentage': 50,
                'last_accessed': firestore.SERVER_TIMESTAMP
            },
            'webdev101': {
                'completion_percentage': 25,
                'last_accessed': firestore.SERVER_TIMESTAMP
            }
        }
    }
]

# Sample data for teacher_details collection
teacher_details_data = [
    {
        'teacher_id': 'user456',
        'name': 'Teacher One',
        'email': 'teacher@example.com',
        'bio': 'Experienced Python and Web Development instructor',
        'expertise': ['Python', 'Web Development', 'JavaScript'],
        'uploaded_courses': [
            {
                'course_id': 'python101',
                'course_name': 'Python Basics'
            },
            {
                'course_id': 'webdev101',
                'course_name': 'Web Development Fundamentals'
            }
        ],
        'ratings': {
            'python101': {
                'average_rating': 4.5,
                'total_reviews': 10
            },
            'webdev101': {
                'average_rating': 4.8,
                'total_reviews': 5
            }
        },
        'payout_info': {
            'bank_account': 'XXXX-XXXX-XXXX-1234',
            'payment_history': [
                {
                    'amount': 500,
                    'date': firestore.SERVER_TIMESTAMP,
                    'for_course': 'python101'
                },
                {
                    'amount': 300,
                    'date': firestore.SERVER_TIMESTAMP,
                    'for_course': 'webdev101'
                }
            ]
        }
    }
]

# Function to add sample data to Firestore
def add_sample_data():
    # Add course_details
    for course in course_details_data:
        db.collection('course_details').document(course['course_id']).set(course)

    # Add users
    for user in users_data:
        db.collection('users').document(user['user_id']).set(user)

    # Add student_details
    for student in student_details_data:
        db.collection('student_details').document(student['student_id']).set(student)

    # Add teacher_details
    for teacher in teacher_details_data:
        db.collection('teacher_details').document(teacher['teacher_id']).set(teacher)

# Call this function to add sample data
add_sample_data()