import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import Dict, Any

def send_alert(
    project_manager_slack_id: str,
    project_health_score: int,
    trello_data: Dict[str, Any],
    git_data: Dict[str, Any],
    slack_data: Dict[str, Any],
    google_calendar_data: Dict[str, Any],
    threshold: int = 70
):
    """
    Sends a detailed alert to the project manager via Slack if the project health score is below a threshold.
    """
    token = os.environ.get("SLACK_API_KEY")
    if not token:
        print("SLACK_API_KEY environment variable is not set. Cannot send alert.")
        return

    if project_health_score < threshold:
        client = WebClient(token=token)

        # Format the message with recent data
        trello_summary = (
            f"- *Overdue Cards:* {trello_data.get('overdue_cards', 'N/A')}\n"
            f"- *Avg. Card Movement (sec):* {trello_data.get('average_list_movement_time', 'N/A'):.2f}\n"
            f"- *Avg. Comments per Card:* {trello_data.get('average_comment_count', 'N/A'):.2f}"
        )

        git_summary = (
            f"- *Avg. Commits per Day:* {sum(git_data.get('commits_per_day', {}).values()) / len(git_data.get('commits_per_day', {})) if git_data.get('commits_per_day') else 'N/A'}\n"
            f"- *Pull Request Comments:* {git_data.get('pull_request_comments', 'N/A')}\n"
            f"- *Lines of Code Changed (30d):* {git_data.get('lines_of_code_changed', 'N/A')}"
        )

        slack_summary = f"- *Average Sentiment:* {slack_data.get('average_sentiment', 'N/A'):.3f}"

        gcal_summary = (
            f"- *Number of Meetings (upcoming):* {google_calendar_data.get('number_of_meetings', 'N/A')}\n"
            f"- *Total Meeting Length (hours):* {google_calendar_data.get('total_meeting_length', 0) / 3600:.2f}"
        )

        message = (
            f":warning: *Project Health Alert* :warning:\n\n"
            f"The health score for your project has dropped to *{project_health_score}* (threshold: {threshold}).\n\n"
            f"*Key Metrics Overview:*\n"
            f"*Trello Insights:*\n{trello_summary}\n\n"
            f"*Git Activity:*\n{git_summary}\n\n"
            f"*Slack Morale:*\n{slack_summary}\n\n"
            f"*Google Calendar Load:*\n{gcal_summary}"
        )

        try:
            client.chat_postMessage(channel=project_manager_slack_id, text=message)
            print(f"Alert sent to Slack channel {project_manager_slack_id}.")
        except SlackApiError as e:
            print(f"Error sending Slack alert to {project_manager_slack_id}: {e.response['error']}")
