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
    return {
        "unread_articles": [
            {"title": "The Ultimate Guide to Python", "tags": ["python", "programming"], "excerpt": "Python is a versatile language that you can use on the backend, frontend, or to build applications. In this guide, we'll walk you through the basics of Python and how to get started with it."},
            {"title": "10 Habits of Highly Effective People", "tags": ["productivity", "self-help"], "excerpt": "In this article, we'll explore the 10 habits of highly effective people and how you can apply them to your own life."},
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
    return {
        "unread_articles": [
            {"title": "The History of the Roman Empire", "tags": ["history", "rome"], "excerpt": "The Roman Empire was one of the most powerful empires in history. In this article, we'll explore its rise and fall."},
            {"title": "The Science of Cooking", "tags": ["science", "cooking"], "excerpt": "Cooking is a science. In this article, we'll explore the chemical reactions that happen when you cook food."},
        ]
    }
