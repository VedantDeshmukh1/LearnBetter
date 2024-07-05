from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import json
from refresh_token import refresh_access_token

def upload_basic():
    """Insert new file.
    Returns : Id of the file uploaded
    """
    # Refresh the token before uploading
    refresh_access_token()

    # Load credentials from the file
    with open('credentials.json', 'r') as cred_file:
        cred_data = json.load(cred_file)
    
    creds = Credentials(
        token=cred_data['access_token'],
        refresh_token=cred_data['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=None,  # Not needed when using refresh token
        client_secret=None,  # Not needed when using refresh token
        scopes=[cred_data['scope']]
    )

    try:
        # create drive api client
        service = build("drive", "v3", credentials=creds)

        # First, check if the "test" folder exists, if not create it
        folder_name = "test"
        folder_id = get_or_create_folder(service, folder_name)

        file_metadata = {
            "name": "NucNwORbPWmQk1WPmt6w_p5ivgke20x.mp4",
            "parents": [folder_id]  # Use the "test" folder ID
        }
        media = MediaFileUpload("NucNwORbPWmQk1WPmt6w_p5ivgke20x.mp4", mimetype="video/mp4")
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields="id"
        ).execute()
        
        print(f'File ID: {file.get("id")}')
        return file.get("id")

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def get_or_create_folder(service, folder_name):
    # Check if folder already exists
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    folders = results.get('files', [])

    if folders:
        # Folder exists, return its ID
        return folders[0]['id']
    else:
        # Folder doesn't exist, create it
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

if __name__ == "__main__":
    upload_basic()