from .online_learning_platform_integration import get_coursera_data, get_udemy_data, get_edx_data
from .reading_app_integration import get_pocket_data, get_instapaper_data
from .google_calendar_integration import get_free_time_slots, schedule_learning_session
from .notion_integration import get_notion_data
from .user_profile import create_user_profile
from .recommendation_engine import get_recommendations
from .calendar_scheduler import schedule_learning_sessions

def get_get_coursera_data():
    return get_coursera_data

def get_get_udemy_data():
    return get_udemy_data

def get_get_edx_data():
    return get_edx_data

def get_get_pocket_data():
    return get_pocket_data

def get_get_instapaper_data():
    return get_instapaper_data

def get_get_notion_data():
    return get_notion_data

def get_create_user_profile():
    return create_user_profile

def get_get_recommendations():
    return get_recommendations

def get_schedule_learning_sessions():
    return schedule_learning_sessions
