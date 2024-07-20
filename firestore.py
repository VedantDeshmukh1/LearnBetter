from firebase_admin import firestore
import firebase_admin
from firebase_admin import credentials, firestore ,storage
import pyrebase
import json
from google.cloud.firestore_v1.types import Timestamp

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

def get_firestore_structure(db, collection_path='', depth=0):
    structure = {}
    collections = db.collection(collection_path).list_documents() if collection_path else db.collections()

    for collection in collections:
        collection_name = collection.id
        structure[collection_name] = {}

        documents = collection.get()
        for doc in documents:
            doc_data = doc.to_dict()
            
            # Expand course_details collection
            if collection_name == 'course_details':
                structure[collection_name][doc.id] = doc_data
            else:
                structure[collection_name][doc.id] = {
                    'fields': list(doc_data.keys()),
                    'subcollections': {}
                }

            if depth > 0:
                subcollections = doc.reference.collections()
                for subcoll in subcollections:
                    structure[collection_name][doc.id]['subcollections'][subcoll.id] = get_firestore_structure(db, f"{collection_path}/{collection_name}/{doc.id}/{subcoll.id}", depth - 1)

    return structure

class FirestoreEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Timestamp):
            return obj.ToDatetime().isoformat()
        return super().default(obj)

# Use the function
firestore_structure = get_firestore_structure(db, depth=3)

# Print the structure
print(json.dumps(firestore_structure, indent=2, cls=FirestoreEncoder))