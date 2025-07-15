import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# This is a placeholder for a real credentials store.
# In a production application, you would store the user's credentials
# in a secure database.
credentials = None

def get_gdrive_credentials():
    """
    Gets the user's Google Drive credentials.
    """
    global credentials
    if credentials:
        return credentials

    # If we don't have credentials, we need to get them from the user.
    # This is a simplified flow for a command-line application.
    # In a web application, you would use a more complex OAuth 2.0 flow.
    flow = Flow.from_client_secrets_file(
        os.environ.get("GOOGLE_CLIENT_SECRETS_FILE"),
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )

    auth_url, _ = flow.authorization_url(prompt='consent')

    print('Please go to this URL: {}'.format(auth_url))
    code = input('Enter the authorization code: ')
    flow.fetch_token(code=code)

    credentials = flow.credentials
    return credentials

def search_gdrive(query: str) -> str:
    """
    Searches Google Drive for the given query.
    """
    try:
        creds = get_gdrive_credentials()
        service = build('drive', 'v3', credentials=creds)

        results = service.files().list(
            q=f"name contains '{query}'",
            pageSize=10,
            fields="nextPageToken, files(id, name, webViewLink)"
        ).execute()

        items = results.get('files', [])

        if not items:
            return "No relevant documents found in Google Drive."

        docs = ""
        for item in items:
            docs += f"- [{item['name']}]({item['webViewLink']})\n"

        return docs
    except Exception as e:
        logger.error(f"Error searching Google Drive: {e}")
        return "Error searching Google Drive."
