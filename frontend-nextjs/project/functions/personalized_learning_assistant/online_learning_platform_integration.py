import os
import requests

def get_coursera_data(user_id):
    """
    Fetches data from a user's Coursera profile.

    Args:
        user_id: The ID of the Coursera user.

    Returns:
        A dictionary containing the Coursera data.
    """
    api_key = os.environ.get("COURSERA_API_KEY")

    if not api_key:
        raise Exception("COURSERA_API_KEY environment variable is not set.")

    # This is a placeholder for the actual Coursera API integration.
    return {
        "enrolled_courses": [
            {"name": "Machine Learning", "progress": 0.5, "skills": ["python", "machine-learning", "data-analysis"]},
            {"name": "Data Science", "progress": 0.2, "skills": ["python", "data-science", "data-analysis"]},
        ]
    }

def get_udemy_data(user_id):
    """
    Fetches data from a user's Udemy profile.

    Args:
        user_id: The ID of the Udemy user.

    Returns:
        A dictionary containing the Udemy data.
    """
    api_key = os.environ.get("UDEMY_API_KEY")

    if not api_key:
        raise Exception("UDEMY_API_KEY environment variable is not set.")

    # This is a placeholder for the actual Udemy API integration.
    return {
        "enrolled_courses": [
            {"name": "Python for Everybody", "progress": 0.8, "skills": ["python", "web-development", "sql"]},
            {"name": "Web Developer Bootcamp", "progress": 0.1, "skills": ["html", "css", "javascript"]},
        ]
    }

def get_edx_data(user_id):
    """
    Fetches data from a user's edX profile.

    Args:
        user_id: The ID of the edX user.

    Returns:
        A dictionary containing the edX data.
    """
    api_key = os.environ.get("EDX_API_KEY")

    if not api_key:
        raise Exception("EDX_API_KEY environment variable is not set.")

    # This is a placeholder for the actual edX API integration.
    return {
        "enrolled_courses": [
            {"name": "Introduction to Computer Science", "progress": 0.9, "skills": ["c", "python", "algorithms"]},
            {"name": "Artificial Intelligence", "progress": 0.3, "skills": ["python", "machine-learning", "search-algorithms"]},
        ]
    }
