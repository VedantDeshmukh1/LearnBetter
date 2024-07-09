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
