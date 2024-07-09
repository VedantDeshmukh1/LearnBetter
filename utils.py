import os
import pickle
import random
import string
import re
from firebase_admin import firestore
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from base64 import urlsafe_b64encode
from firebase_admin import firestore
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

def refresh_access_token():
    # Load the current credentials
    with open('credentials.json', 'r') as file:
        cred_data = json.load(file)

    # Create a Credentials object
    creds = Credentials(
        token=cred_data['access_token'],
        refresh_token=cred_data['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cred_data.get('client_id'),  # Add these if you have them
        client_secret=cred_data.get('client_secret'),  # Add these if you have them
        scopes=[cred_data['scope']]
    )

    # Refresh the token
    if creds.expired:
        creds.refresh(Request())

    # Update the credentials file with the new access token
    cred_data['access_token'] = creds.token
    with open('credentials.json', 'w') as file:
        json.dump(cred_data, file, indent=2)

    print("Access token refreshed and updated in credentials.json")


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

SCOPES = ['https://mail.google.com/']
our_email = 'learnbetter310@gmail.com'

def gmail_authenticate():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials_email.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def send_email(to, subject, body):
    service = gmail_authenticate()
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    message['from'] = our_email
    raw_message = urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    try:
        message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        print(f"Message Id: {message['id']}")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False