from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import json

def upload_basic():
    """Insert new file.
    Returns : Id of the file uploaded
    """
    # Load credentials from the file
    with open('credentials.json', 'r') as cred_file:
        cred_data = json.load(cred_file)
    
    creds = Credentials(
        token=cred_data['access_token'],
        refresh_token=cred_data['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET"
    )

    try:
        # create drive api client
        service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": "NucNwORbPWmQk1WPmt6w_p5ivgke20x.mp4",
            "parents": ["root"]  # Upload to root folder, change if needed
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

if __name__ == "__main__":
    upload_basic()