from trello_integration import get_trello_data
from git_integration import get_git_data
from slack_integration import get_slack_data
from google_calendar_integration import get_google_calendar_data

def calculate_project_health_score(trello_board_id, git_repo_path, slack_channel_id, google_calendar_id):
    """
    Calculates the project health score.

    Args:
        trello_board_id: The ID of the Trello board.
        git_repo_path: The path to the Git repository.
        slack_channel_id: The ID of the Slack channel.
        google_calendar_id: The ID of the Google Calendar.

    Returns:
        The project health score.
    """
    trello_data = get_trello_data(trello_board_id)
    git_data = get_git_data(git_repo_path)
    slack_data = get_slack_data(slack_channel_id)
    google_calendar_data = get_google_calendar_data(google_calendar_id)

    # This is a simple scoring system. It can be improved with more sophisticated logic.
    score = 100

    # Trello score
    if trello_data["overdue_cards"] > 5:
        score -= 10
    if trello_data["average_list_movement_time"] > 86400:  # 1 day
        score -= 10
    if trello_data["average_comment_count"] < 1:
        score -= 10

    # Git score
    if git_data["commits_today"] < 1:
        score -= 10
    if git_data["lines_of_code_changed"] < 100:
        score -= 10

    # Slack score
    if slack_data["average_sentiment"] < 0:
        score -= 10

    # Google Calendar score
    if google_calendar_data["meeting_count"] > 10:
        score -= 10
    if google_calendar_data["total_meeting_duration"] > 36000:  # 10 hours
        score -= 10

    return score
