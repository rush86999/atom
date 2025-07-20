from fastapi import FastAPI
from project_health_score import calculate_project_health_score
from alerting import send_alert

app = FastAPI()

@app.post("/project-health")
def project_health(trello_board_id: str, git_repo_path: str, slack_channel_id: str, google_calendar_id: str, project_manager_email: str):
    """
    Calculates the project health score and sends an alert if necessary.
    """
    project_health_score = calculate_project_health_score(trello_board_id, git_repo_path, slack_channel_id, google_calendar_id)

    if project_health_score < 70:
        send_alert(project_manager_email, project_health_score)

    return {"project_health_score": project_health_score}
