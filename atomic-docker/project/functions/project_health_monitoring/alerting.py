import os
import smtplib

def send_alert(project_manager_email, project_health_score, trello_data, git_data, slack_data, google_calendar_data):
    """
    Sends an alert to the project manager.

    Args:
        project_manager_email: The email address of the project manager.
        project_health_score: The project health score.
        trello_data: A dictionary containing the Trello data.
        git_data: A dictionary containing the Git data.
        slack_data: A dictionary containing the Slack data.
        google_calendar_data: A dictionary containing the Google Calendar data.
    """
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        raise Exception("SENDER_EMAIL and SENDER_PASSWORD environment variables are not set.")

    message = f"""\
Subject: Project Health Alert

The health score for your project has dropped to {project_health_score}.

Here are some details:

Trello:
- Overdue cards: {trello_data['overdue_cards']}
- Average list movement time: {trello_data['average_list_movement_time']}
- Average comment count: {trello_data['average_comment_count']}

Git:
- Commits today: {git_data['commits_today']}
- Lines of code changed: {git_data['lines_of_code_changed']}

Slack:
- Average sentiment: {slack_data['average_sentiment']}

Google Calendar:
- Meeting count: {google_calendar_data['meeting_count']}
- Total meeting duration: {google_calendar_data['total_meeting_duration']}
"""

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, project_manager_email, message)
