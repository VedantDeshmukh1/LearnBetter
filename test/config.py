import firebase_admin
from firebase_admin import credentials, firestore ,storage
import pyrebase

# Firebase configuration for pyrebase
firebase_config = {
    "apiKey": "AIzaSyBWWgEmrT_RcCRcfiSSNk_mmGtmsx7JtpQ",
    "authDomain": "learnbetter-acad7.firebaseapp.com",
    "databaseURL": "https://learnbetter-acad7-default-rtdb.firebaseio.com",
    "projectId": "learnbetter-acad7",
    "storageBucket": "learnbetter-acad7.appspot.com",
    "messagingSenderId": "519730804377",
    "appId": "1:519730804377:web:ab5b8f33072ae851ba6a08",
    "measurementId": "G-RK211QSS71"
}

# Initialize Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
rdb = firebase.database()
#Initializing storage


# Initialize Firebase Admin SDK
cred = credentials.Certificate("learnbetter-acad7-firebase-adminsdk-36uok-bc0c7e1ebd.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
bucket = storage.bucket('learnbetter-acad7.appspot.com')