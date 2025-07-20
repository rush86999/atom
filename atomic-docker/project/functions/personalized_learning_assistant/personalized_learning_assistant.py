from online_learning_platform_integration import get_coursera_data, get_udemy_data, get_edx_data
from reading_app_integration import get_pocket_data, get_instapaper_data
from google_calendar_integration import find_free_time
from notion_integration import analyze_notes

def generate_personalized_learning_plan(coursera_user_id, udemy_user_id, edx_user_id, pocket_consumer_key, pocket_access_token, instapaper_consumer_key, instapaper_consumer_secret, instapaper_oauth_token, instapaper_oauth_token_secret, google_calendar_id, notion_database_id, learning_duration_minutes):
    """
    Generates a personalized learning plan.

    Args:
        coursera_user_id: The ID of the Coursera user.
        udemy_user_id: The ID of the Udemy user.
        edx_user_id: The ID of the edX user.
        pocket_consumer_key: The consumer key for the Pocket API.
        pocket_access_token: The access token for the Pocket API.
        instapaper_consumer_key: The consumer key for the Instapaper API.
        instapaper_consumer_secret: The consumer secret for the Instapaper API.
        instapaper_oauth_token: The OAuth token for the Instapaper API.
        instapaper_oauth_token_secret: The OAuth token secret for the Instapaper API.
        google_calendar_id: The ID of the Google Calendar.
        notion_database_id: The ID of the Notion database containing the user's notes.
        learning_duration_minutes: The duration of each learning session in minutes.

    Returns:
        A dictionary containing the personalized learning plan.
    """
    coursera_data = get_coursera_data(coursera_user_id)
    udemy_data = get_udemy_data(udemy_user_id)
    edx_data = get_edx_data(edx_user_id)
    pocket_data = get_pocket_data()
    instapaper_data = get_instapaper_data()
    free_time_slots = find_free_time(google_calendar_id, learning_duration_minutes)
    analysis_results = analyze_notes(notion_database_id)

    recommended_courses = []
    for course in coursera_data["enrolled_courses"]:
        if course["progress"] < 1.0:
            recommended_courses.append(course)
    for course in udemy_data["enrolled_courses"]:
        if course["progress"] < 1.0:
            recommended_courses.append(course)
    for course in edx_data["enrolled_courses"]:
        if course["progress"] < 1.0:
            recommended_courses.append(course)

    recommended_articles = []
    for article in pocket_data["unread_articles"]:
        recommended_articles.append(article)
    for article in instapaper_data["unread_articles"]:
        recommended_articles.append(article)

    learning_schedule = []
    for slot in free_time_slots:
        if recommended_courses:
            learning_schedule.append({
                "start": slot["start"],
                "end": slot["end"],
                "activity": f"Work on {recommended_courses.pop(0)['name']}"
            })
        elif recommended_articles:
            learning_schedule.append({
                "start": slot["start"],
                "end": slot["end"],
                "activity": f"Read {recommended_articles.pop(0)['title']}"
            })

    return {
        "recommended_courses": recommended_courses,
        "recommended_articles": recommended_articles,
        "learning_schedule": learning_schedule,
    }
