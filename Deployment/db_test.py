import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Replace 'path/to/your/serviceAccountKey.json' with the actual path
cred = credentials.Certificate('learnbetter-acad7-firebase-adminsdk-36uok-bc0c7e1ebd.json')
firebase_admin.initialize_app(cred)

db = firestore.client()


# Get a reference to a collection
users_ref = db.collection('users')

# Add a new document
users_ref.add({
    'name': 'Jane Doe',
    'age': 25
})

# Get a document by ID
user_ref = db.collection('users').document('user-id')
user = user_ref.get()
print(user.to_dict())
