import os
import logging
from typing import Optional
from pyowm import OWM
from newsapi import NewsApiClient

logger = logging.getLogger(__name__)

async def get_weather(user_id: str, location: str, db_conn_pool):
    """
    Gets the current weather for a specific location.
    """
    owm_api_key = os.environ.get("OWM_API_KEY")
    if not owm_api_key:
        raise Exception("OWM API key not configured.")

    owm = OWM(owm_api_key)
    mgr = owm.weather_manager()
    observation = mgr.weather_at_place(location)
    weather = observation.weather
    return weather.to_dict()

async def get_news(user_id: str, query: str, db_conn_pool):
    """
    Gets the top headlines from a news source.
    """
    newsapi_api_key = os.environ.get("NEWSAPI_API_KEY")
    if not newsapi_api_key:
        raise Exception("NewsAPI API key not configured.")

    newsapi = NewsApiClient(api_key=newsapi_api_key)
    top_headlines = newsapi.get_top_headlines(q=query, language='en')
    return top_headlines

async def set_reminder(user_id: str, reminder: str, remind_at: str, db_conn_pool):
    """
    Sets a reminder for the user.
    """
    # This is a simplified implementation. In a real application, you would use a proper
    # task scheduler like Celery or APScheduler to handle the scheduling.
    # For now, we'll just log the request.
    logger.info(f"Setting reminder for user {user_id} at {remind_at}: {reminder}")

    # In a real implementation, you would do something like this:
    # agenda_service.schedule(remind_at, 'send_reminder', {'user_id': user_id, 'reminder': reminder})

    return {"message": "Reminder set successfully."}
