from fastapi import FastAPI
from project_health_score import calculate_project_health_score
from alerting import send_alert
from trello_integration import get_trello_data
from git_integration import get_git_data
from slack_integration import get_slack_data
from google_calendar_integration import get_google_calendar_data
from dependencies import install_dependencies

install_dependencies()

app = FastAPI()

@app.post("/project-health")
def project_health(trello_board_id: str, git_repo_path: str, slack_channel_id: str, google_calendar_id: str, project_manager_email: str):
    """
    Calculates the project health score and sends an alert if necessary.
    """
    trello_data = get_trello_data(trello_board_id)
    git_data = get_git_data(git_repo_path)
    slack_data = get_slack_data(slack_channel_id)
    google_calendar_data = get_google_calendar_data(google_calendar_id)

    project_health_score = calculate_project_health_score(trello_data, git_data, slack_data, google_calendar_data)

    if project_health_score < 70:
        send_alert(project_manager_email, project_health_score, trello_data, git_data, slack_data, google_calendar_data)

    return {"project_health_score": project_health_score}
