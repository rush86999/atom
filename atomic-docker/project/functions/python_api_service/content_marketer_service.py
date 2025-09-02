import logging
from . import gdrive_service
from . import wordpress_service # We need to create this
from . import trello_service

logger = logging.getLogger(__name__)

async def create_wordpress_post_from_google_drive_document(user_id: str, google_drive_document_id: str, db_conn_pool):
    """
    Creates a WordPress post from a Google Drive document.
    """
    gdrive_creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
    if not gdrive_creds:
        raise Exception("Could not get authenticated Google Drive client.")

    file_content, metadata = await gdrive_service.download_file(gdrive_creds, google_drive_document_id)

    wordpress_client = await wordpress_service.get_wordpress_client(user_id, db_conn_pool)
    if not wordpress_client:
        raise Exception("Could not get authenticated WordPress client.")

    post_data = {
        "title": metadata['name'],
        "content": file_content.decode('utf-8'),
        "status": "draft"
    }

    post = await wordpress_service.create_post(wordpress_client, post_data)
    return post

async def get_wordpress_post_summary(user_id: str, post_id: str, db_conn_pool):
    """
    Gets a summary of a WordPress post.
    """
    wordpress_client = await wordpress_service.get_wordpress_client(user_id, db_conn_pool)
    if not wordpress_client:
        raise Exception("Could not get authenticated WordPress client.")

    post = await wordpress_service.get_post(wordpress_client, post_id)
    return post

async def create_trello_card_from_wordpress_post(user_id: str, post_id: str, trello_list_id: str, db_conn_pool):
    """
    Creates a Trello card for a new WordPress post.
    """
    wordpress_client = await wordpress_service.get_wordpress_client(user_id, db_conn_pool)
    if not wordpress_client:
        raise Exception("Could not get authenticated WordPress client.")

    post = await wordpress_service.get_post(wordpress_client, post_id)

    trello_api_key, trello_token = await trello_service.get_trello_credentials(user_id, db_conn_pool)
    if not trello_api_key or not trello_token:
        raise Exception("Could not get Trello credentials.")

    card_name = f"New Post: {post.title}"
    card_desc = f"**Post ID:** {post.id}\n**Link:** {post.link}"

    card = await trello_service.create_card(trello_api_key, trello_token, trello_list_id, card_name, card_desc)
    return card
