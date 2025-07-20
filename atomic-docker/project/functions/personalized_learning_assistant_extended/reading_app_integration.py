import os
import requests

def get_pocket_data():
    """
    Fetches data from a user's Pocket account.

    Returns:
        A dictionary containing the Pocket data.
    """
    consumer_key = os.environ.get("POCKET_CONSUMER_KEY")
    access_token = os.environ.get("POCKET_ACCESS_TOKEN")

    if not consumer_key or not access_token:
        raise Exception("POCKET_CONSUMER_KEY and POCKET_ACCESS_TOKEN environment variables are not set.")

    # This is a placeholder for the actual Pocket API integration.
    # url = "https://getpocket.com/v3/get"
    # params = {
    #     "consumer_key": consumer_key,
    #     "access_token": access_token,
    #     "state": "unread",
    #     "detailType": "complete",
    # }
    # response = requests.post(url, json=params)
    # response.raise_for_status()
    # return response.json()

    return {
        "unread_articles": [
            {"title": "The Ultimate Guide to Python", "tags": ["python", "programming"]},
            {"title": "10 Habits of Highly Effective People", "tags": ["productivity", "self-help"]},
        ]
    }

def get_instapaper_data():
    """
    Fetches data from a user's Instapaper account.

    Returns:
        A dictionary containing the Instapaper data.
    """
    consumer_key = os.environ.get("INSTAPAPER_CONSUMER_KEY")
    consumer_secret = os.environ.get("INSTAPAPER_CONSUMER_SECRET")
    oauth_token = os.environ.get("INSTAPAPER_OAUTH_TOKEN")
    oauth_token_secret = os.environ.get("INSTAPAPER_OAUTH_TOKEN_SECRET")

    if not consumer_key or not consumer_secret or not oauth_token or not oauth_token_secret:
        raise Exception("Instapaper API keys are not set.")

    # This is a placeholder for the actual Instapaper API integration.
    # from instapaper import Instapaper
    # client = Instapaper(consumer_key, consumer_secret, oauth_token, oauth_token_secret)
    # bookmarks = client.bookmarks.list()
    # return {"unread_articles": [{"title": b.title, "tags": b.tags} for b in bookmarks]}

    return {
        "unread_articles": [
            {"title": "The History of the Roman Empire", "tags": ["history", "rome"]},
            {"title": "The Science of Cooking", "tags": ["science", "cooking"]},
        ]
    }
