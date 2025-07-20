import os
from slack_sdk import WebClient

def send_alert(project_manager_slack_id, project_health_score, trello_data, git_data, slack_data, google_calendar_data):
    """
    Sends an alert to the project manager if the project health score is below a certain threshold.

    Args:
        project_manager_slack_id: The Slack ID of the project manager.
        project_health_score: The project health score.
        trello_data: A dictionary containing the Trello data.
        git_data: A dictionary containing the Git data.
        slack_data: A dictionary containing the Slack data.
        google_calendar_data: A dictionary containing the Google Calendar data.
    """
    api_key = os.environ.get("SLACK_API_KEY")

    if not api_key:
        raise Exception("SLACK_API_KEY environment variable is not set.")

    client = WebClient(token=api_key)

    if project_health_score < 70:
        message = f"""
        :warning: Project Health Alert :warning:

        The health score for your project has dropped to {project_health_score}.

        Here are some of the contributing factors:
        - Trello:
            - Overdue cards: {trello_data['overdue_cards']}
            - Average list movement time: {trello_data['average_list_movement_time']}
            - Average comment count: {trello_data['average_comment_count']}
        - Git:
            - Commits per day: {git_data['commits_per_day']}
            - Pull request comments: {git_data['pull_request_comments']}
            - Lines of code changed: {git_data['lines_of_code_changed']}
        - Slack:
            - Average sentiment: {slack_data['average_sentiment']}
        - Google Calendar:
            - Meeting count: {google_calendar_data['meeting_count']}
            - Average meeting duration: {google_calendar_data['average_meeting_duration']}
        """
        client.chat_postMessage(channel=project_manager_slack_id, text=message)
