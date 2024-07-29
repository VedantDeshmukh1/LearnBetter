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
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

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
    if os.path.exists("credentials/token.json"):
        creds = Credentials.from_authorized_user_file("credentials/token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials/credentials_email.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open("credentials/token.json", "w") as token:
            token.write(creds.to_json())
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

def get_drive_service():
    """Return an authenticated Google Drive service object."""
    gauth = GoogleAuth()
    
    # Try to load saved client credentials
    creds_file = "credentials/mycreds.txt"
    if os.path.exists(creds_file):
        gauth.LoadCredentialsFile(creds_file)
    
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.GetFlow()
        gauth.flow.params.update({'access_type': 'offline'})
        gauth.flow.params.update({'approval_prompt': 'force'})
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh them if expired
        try:
            gauth.Refresh()
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            # If refresh fails, re-authenticate
            gauth.GetFlow()
            gauth.flow.params.update({'access_type': 'offline'})
            gauth.flow.params.update({'approval_prompt': 'force'})
            gauth.LocalWebserverAuth()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    
    # Save the current credentials to a file
    gauth.SaveCredentialsFile(creds_file)
    
    return GoogleDrive(gauth)

def upload_to_drive(file_path, file_name, course_id, course_name):
    """Upload file to Google Drive and return the sharing link."""
    drive = get_drive_service()

    # Create or get the "courses" folder
    courses_folder = get_or_create_folder(drive, "courses")

    # Create or get the course-specific folder within "courses"
    course_folder_name = f"{course_id}_{course_name}"
    course_folder = get_or_create_folder(drive, course_folder_name, parent_id=courses_folder['id'])

    # Create the file
    file = drive.CreateFile({
        'title': file_name,
        'parents': [{'id': course_folder['id']}]
    })
    file.SetContentFile(file_path)
    file.Upload()

    # Set the file to be publicly accessible
    file.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })

    # Get the sharing link
    file.FetchMetadata()
    sharing_link = file['alternateLink']
    modified_link = sharing_link.replace("view?usp=drivesdk", "preview")
    return modified_link

def get_or_create_folder(drive, folder_name, parent_id=None):
    """Check if folder exists in Google Drive, if not create it."""
    query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    file_list = drive.ListFile({'q': query}).GetList()

    if file_list:
        # Folder exists, return it
        return file_list[0]
    else:
        # Folder doesn't exist, create it
        folder = drive.CreateFile({
            'title': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        })
        if parent_id:
            folder['parents'] = [{'id': parent_id}]
        folder.Upload()
        return folder

def get_drive_file_id(url):
    """Extract and return the file ID from the Google Drive URL."""
    if '/file/d/' in url:
        return url.split('/file/d/')[1].split('/')[0]
    elif 'id=' in url:
        return url.split('id=')[1]
    return None