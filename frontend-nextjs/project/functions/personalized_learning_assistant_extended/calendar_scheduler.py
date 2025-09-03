from .google_calendar_integration import get_free_time_slots, schedule_learning_session
import datetime

def schedule_learning_sessions(calendar_id, recommendations, duration_minutes):
    """
    Schedules learning sessions in the user's calendar.

    Args:
        calendar_id: The ID of the Google Calendar.
        recommendations: A dictionary containing the recommendations.
        duration_minutes: The duration of each learning session in minutes.
    """
    now = datetime.datetime.utcnow()
    start_of_week = now - datetime.timedelta(days=now.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)

    free_slots = get_free_time_slots(calendar_id, start_of_week, end_of_week, duration_minutes)

    for i, slot in enumerate(free_slots):
        if i < len(recommendations["courses"]):
            schedule_learning_session(
                calendar_id,
                slot["start"],
                slot["start"] + datetime.timedelta(minutes=duration_minutes),
                f"Learning Session: {recommendations['courses'][i]}",
                f"A learning session for the course: {recommendations['courses'][i]}",
            )
        elif i < len(recommendations["courses"]) + len(recommendations["articles"]):
            article_index = i - len(recommendations["courses"])
            schedule_learning_session(
                calendar_id,
                slot["start"],
                slot["start"] + datetime.timedelta(minutes=duration_minutes),
                f"Learning Session: {recommendations['articles'][article_index]}",
                f"A learning session for the article: {recommendations['articles'][article_index]}",
            )
        elif i < len(recommendations["courses"]) + len(recommendations["articles"]) + len(recommendations["books"]):
            book_index = i - len(recommendations["courses"]) - len(recommendations["articles"])
            schedule_learning_session(
                calendar_id,
                slot["start"],
                slot["start"] + datetime.timedelta(minutes=duration_minutes),
                f"Learning Session: {recommendations['books'][book_index]}",
                f"A learning session for the book: {recommendations['books'][book_index]}",
            )
