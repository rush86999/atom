import logging
import httpx
from . import trello_service
from . import gdrive_service

logger = logging.getLogger(__name__)

async def create_google_drive_folder_from_trello_board(user_id: str, board_id: str, db_conn_pool):
    """
    Creates a Google Drive folder for a new Trello board.
    """
    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    board = await trello_service.get_board(trello_api_key, trello_token, board_id) # We need to add this to trello_service.py

    gdrive_creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
    if not gdrive_creds:
        raise Exception("Could not get authenticated Google Drive client.")

    folder_metadata = {
        'name': board['name'],
        'mimeType': 'application/vnd.google-apps.folder'
    }

    folder = await gdrive_service.create_file(gdrive_creds, folder_metadata) # We need to add this to gdrive_service.py
    return folder

async def upload_trello_attachments_to_google_drive(user_id: str, card_id: str, folder_id: str, db_conn_pool):
    """
    Uploads Trello card attachments to a Google Drive folder.
    """
    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    attachments = await trello_service.get_attachments(trello_api_key, trello_token, card_id) # We need to add this to trello_service.py

    gdrive_creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
    if not gdrive_creds:
        raise Exception("Could not get authenticated Google Drive client.")

    uploaded_files = []
    for attachment in attachments:
        async with httpx.AsyncClient() as client:
            response = await client.get(attachment['url'])
            response.raise_for_status()
            file_content = response.content

        file_metadata = {
            'name': attachment['name'],
            'parents': [folder_id]
        }

        uploaded_file = await gdrive_service.create_file(gdrive_creds, file_metadata, file_content)
        uploaded_files.append(uploaded_file)

    return {"message": "Attachments uploaded successfully.", "files": uploaded_files}

async def create_trello_board_from_google_drive_folder(user_id: str, folder_id: str, db_conn_pool):
    """
    Creates a Trello board from a Google Drive folder.
    """
    gdrive_creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
    if not gdrive_creds:
        raise Exception("Could not get authenticated Google Drive client.")

    folder = await gdrive_service.get_file(gdrive_creds, folder_id) # We need to add this to gdrive_service.py

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    board = await trello_service.create_board(trello_api_key, trello_token, folder['name']) # We need to add this to trello_service.py
    return board

async def create_trello_card_for_new_file_in_google_drive(user_id: str, folder_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for each new file added to a Google Drive folder.
    """
    # This is a simplified implementation. In a real application, you would use Google Drive's push notifications
    # to trigger this function whenever a new file is added to the folder.
    # For now, we'll just list the files in the folder and create a card for each one.
    gdrive_creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
    if not gdrive_creds:
        raise Exception("Could not get authenticated Google Drive client.")

    files = await gdrive_service.list_files(gdrive_creds, folder_id=folder_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    created_cards = []
    for file in files['files']:
        card_name = f"New file: {file['name']}"
        card_desc = f"A new file has been added to the Google Drive folder.\n\n**File Name:** {file['name']}\n**Link:** {file['webViewLink']}"
        card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
        created_cards.append(card)

    return {"message": "Cards created successfully.", "cards": created_cards}
