from fastapi import FastAPI
from project_health_score import calculate_project_health_score
from alerting import send_alert
from trello_integration import get_trello_data
from git_integration import get_git_data
from slack_integration import get_slack_data
from google_calendar_integration import get_google_calendar_data
from dependencies import install_dependencies
from scheduler import start_scheduler

install_dependencies()

app = FastAPI()

start_scheduler()

from database import get_db_connection

@app.post("/configurations")
def create_configuration(trello_board_id: str, git_repo_path: str, slack_channel_id: str, google_calendar_id: str, project_manager_email: str):
    """
    Creates a new project health monitoring configuration.
    """
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO configurations (trello_board_id, git_repo_path, slack_channel_id, google_calendar_id, project_manager_email) VALUES (?, ?, ?, ?, ?)",
        (trello_board_id, git_repo_path, slack_channel_id, google_calendar_id, project_manager_email),
    )
    conn.commit()
    conn.close()
    return {"message": "Configuration created successfully."}

@app.get("/configurations")
def get_configurations():
    """
    Returns all project health monitoring configurations.
    """
    conn = get_db_connection()
    configurations = conn.execute("SELECT * FROM configurations").fetchall()
    conn.close()
    return configurations

@app.put("/configurations/{configuration_id}")
def update_configuration(configuration_id: int, trello_board_id: str, git_repo_path: str, slack_channel_id: str, google_calendar_id: str, project_manager_email: str):
    """
    Updates a project health monitoring configuration.
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE configurations SET trello_board_id = ?, git_repo_path = ?, slack_channel_id = ?, google_calendar_id = ?, project_manager_email = ? WHERE id = ?",
        (trello_board_id, git_repo_path, slack_channel_id, google_calendar_id, project_manager_email, configuration_id),
    )
    conn.commit()
    conn.close()
    return {"message": "Configuration updated successfully."}

@app.delete("/configurations/{configuration_id}")
def delete_configuration(configuration_id: int):
    """
    Deletes a project health monitoring configuration.
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM configurations WHERE id = ?", (configuration_id,))
    conn.commit()
    conn.close()
    return {"message": "Configuration deleted successfully."}

def project_health():
    """
    Calculates the project health score for all configurations and sends an alert if necessary.
    """
    conn = get_db_connection()
    configurations = conn.execute("SELECT * FROM configurations").fetchall()
    conn.close()

    for configuration in configurations:
        trello_data = get_trello_data(configuration["trello_board_id"])
        git_data = get_git_data(configuration["git_repo_path"])
        slack_data = get_slack_data(configuration["slack_channel_id"])
        google_calendar_data = get_google_calendar_data(configuration["google_calendar_id"])

        project_health_score = calculate_project_health_score(trello_data, git_data, slack_data, google_calendar_data)

        if project_health_score < 70:
            send_alert(configuration["project_manager_email"], project_health_score, trello_data, git_data, slack_data, google_calendar_data)
