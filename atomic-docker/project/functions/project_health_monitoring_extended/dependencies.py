from .trello_integration import get_trello_data
from .git_integration import get_git_data
from .slack_integration import get_slack_data
from .google_calendar_integration import get_google_calendar_data
from .project_health_score import calculate_project_health_score
from .alerting import send_alert

def get_get_trello_data():
    return get_trello_data

def get_get_git_data():
    return get_git_data

def get_get_slack_data():
    return get_slack_data

def get_get_google_calendar_data():
    return get_google_calendar_data

def get_calculate_project_health_score():
    return calculate_project_health_score

def get_send_alert():
    return send_alert
