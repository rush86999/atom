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
    # url = f"https://api.coursera.org/api/users/{user_id}/courses"
    # headers = {"Authorization": f"Bearer {api_key}"}
    # response = requests.get(url, headers=headers)
    # response.raise_for_status()
    # return response.json()

    return {
        "enrolled_courses": [
            {"name": "Machine Learning", "progress": 0.5},
            {"name": "Data Science", "progress": 0.2},
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
    # url = f"https://www.udemy.com/api-2.0/users/{user_id}/courses"
    # headers = {"Authorization": f"Bearer {api_key}"}
    # response = requests.get(url, headers=headers)
    # response.raise_for_status()
    # return response.json()

    return {
        "enrolled_courses": [
            {"name": "Python for Everybody", "progress": 0.8},
            {"name": "Web Developer Bootcamp", "progress": 0.1},
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
    # url = f"https://api.edx.org/api/user/v1/accounts/{user_id}/course_enrollments"
    # headers = {"Authorization": f"Bearer {api_key}"}
    # response = requests.get(url, headers=headers)
    # response.raise_for_status()
    # return response.json()

    return {
        "enrolled_courses": [
            {"name": "Introduction to Computer Science", "progress": 0.9},
            {"name": "Artificial Intelligence", "progress": 0.3},
        ]
    }
