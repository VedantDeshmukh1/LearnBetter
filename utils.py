import random
import string
import re
from firebase_admin import firestore

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

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def validate_name(name):
    return len(name) >= 2

def update_course_ratings(course_ref, new_rating):
    course = course_ref.get().to_dict()
    new_total_ratings = course['total_ratings'] + 1
    new_rating_sum = (course['average_rating'] * course['total_ratings']) + new_rating
    new_average_rating = new_rating_sum / new_total_ratings
    
    course_ref.update({
        'total_ratings': firestore.Increment(1),
        'average_rating': new_average_rating
    })

def generate_video_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))