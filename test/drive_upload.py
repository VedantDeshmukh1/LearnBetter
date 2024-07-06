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
        client_id=cred_data.get('client_id'),  # Pass client_id from credentials
        client_secret=cred_data.get('client_secret'),  # Pass client_secret from credentials
        scopes=[cred_data['scope']]
    )

    try:
        # create drive api client
        service = build("drive", "v3", credentials=creds)

        # First, check if the "test" folder exists, if not create it
        folder_name = "test"
        folder_id = get_or_create_folder(service, folder_name)

        file_metadata = {
            "name": "kanishk_arya_assignment_submission.mov",
            "parents": [folder_id]  # Use the "test" folder ID
        }
        media = MediaFileUpload("kanishk_arya_assignment_submission.mov", mimetype="video/mov")
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields="id, webViewLink" # Request webViewLink field
        ).execute()
        
        print(f'File ID: {file.get("id")}')
        sharing_link = file.get("webViewLink")
        modified_link = sharing_link.replace("/view?usp=drivesdk", "/preview?")
        print(f'Sharing Link: {sharing_link}')
        print(f'Modified Sharing Link: {modified_link}')
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