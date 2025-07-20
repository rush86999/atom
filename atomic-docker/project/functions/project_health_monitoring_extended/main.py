from fastapi import FastAPI, Depends, HTTPException
from .dependencies import (
    get_get_trello_data,
    get_get_git_data,
    get_get_slack_data,
    get_get_google_calendar_data,
    get_calculate_project_health_score,
    get_send_alert,
)

app = FastAPI()

@app.post("/project-health")
def project_health(
    trello_board_id: str,
    git_repo_path: str,
    slack_channel_id: str,
    google_calendar_id: str,
    project_manager_slack_id: str,
    get_trello_data: callable = Depends(get_get_trello_data),
    get_git_data: callable = Depends(get_get_git_data),
    get_slack_data: callable = Depends(get_get_slack_data),
    get_google_calendar_data: callable = Depends(get_get_google_calendar_data),
    calculate_project_health_score: callable = Depends(get_calculate_project_health_score),
    send_alert: callable = Depends(get_send_alert),
):
    """
    Calculates the project health score and sends an alert if necessary.
    """
    try:
        trello_data = get_trello_data(trello_board_id)
        git_data = get_git_data(git_repo_path)
        slack_data = get_slack_data(slack_channel_id)
        google_calendar_data = get_google_calendar_data(google_calendar_id)

        project_health_score = calculate_project_health_score(
            trello_data,
            git_data,
            slack_data,
            google_calendar_data,
        )

        send_alert(
            project_manager_slack_id,
            project_health_score,
            trello_data,
            git_data,
            slack_data,
            google_calendar_data,
        )

        return {"project_health_score": project_health_score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
