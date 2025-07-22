from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from trello_integration import get_trello_data
from git_integration import get_git_data
from slack_integration import get_slack_data
from google_calendar_integration import get_google_calendar_data
from project_health_score import calculate_project_health_score
from alerting import send_alert

app = FastAPI()

class ProjectIdentifiers(BaseModel):
    trello_board_id: str
    git_repo_path: str
    github_repo_name: str # e.g., "owner/repo"
    slack_channel_id: str
    google_calendar_id: str
    project_manager_slack_id: str

@app.post("/project-health/")
async def project_health(ids: ProjectIdentifiers):
    """
    Endpoint to calculate and return the project health score.
    It fetches data from all integrated sources, calculates a score,
    and sends an alert if the score is below a certain threshold.
    """
    try:
        trello_data = get_trello_data(ids.trello_board_id)
        git_data = get_git_data(ids.git_repo_path, ids.github_repo_name)
        slack_data = get_slack_data(ids.slack_channel_id)
        google_calendar_data = get_google_calendar_data(ids.google_calendar_id)

        if any(data.get("error") for data in [trello_data, git_data, slack_data, google_calendar_data]):
            raise HTTPException(status_code=500, detail="Error fetching data from one or more integrations.")

        score = calculate_project_health_score(trello_data, git_data, slack_data, google_calendar_data)

        send_alert(
            project_manager_slack_id=ids.project_manager_slack_id,
            project_health_score=score,
            trello_data=trello_data,
            git_data=git_data,
            slack_data=slack_data,
            google_calendar_data=google_calendar_data
        )

        return {"project_health_score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
