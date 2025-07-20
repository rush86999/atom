def calculate_project_health_score(trello_data, git_data, slack_data, google_calendar_data):
    """
    Calculates the project health score based on data from different sources.

    Args:
        trello_data: A dictionary containing the Trello data.
        git_data: A dictionary containing the Git data.
        slack_data: A dictionary containing the Slack data.
        google_calendar_data: A dictionary containing the Google Calendar data.

    Returns:
        The project health score.
    """
    score = 100

    # Trello metrics
    if trello_data["overdue_cards"] > 5:
        score -= 10
    if trello_data["average_list_movement_time"] > 86400:  # 1 day
        score -= 10
    if trello_data["average_comment_count"] < 1:
        score -= 5

    # Git metrics
    if sum(git_data["commits_per_day"].values()) / len(git_data["commits_per_day"]) < 1:
        score -= 20
    # Placeholder for pull request comments and lines of code changes
    if git_data["pull_request_comments"] < 1:
        score -= 10
    if git_data["lines_of_code_changed"] < 100:
        score -= 5

    # Slack metrics
    if slack_data["average_sentiment"] < 0:
        score -= 20

    # Google Calendar metrics
    if google_calendar_data["meeting_count"] > 10:
        score -= 10
    if google_calendar_data["average_meeting_duration"] > 3600:  # 1 hour
        score -= 10

    return max(0, score)
