from typing import Dict, Any

def calculate_project_health_score(
    trello_data: Dict[str, Any],
    git_data: Dict[str, Any],
    slack_data: Dict[str, Any],
    google_calendar_data: Dict[str, Any]
) -> int:
    """
    Calculates a project health score based on data from various sources.

    The scoring is based on a weighted system where a perfect score is 100.
    Points are deducted for metrics that indicate poor project health.
    """
    score = 100
    weights = {
        "trello_overdue": 2,
        "trello_movement": 1,
        "trello_comments": 1,
        "git_commits": 2.5,
        "git_pr_comments": 1.5,
        "git_code_churn": 0.5,
        "slack_sentiment": 3,
        "gcal_meeting_count": 1,
        "gcal_meeting_length": 1,
    }

    # Trello scoring
    if trello_data.get("overdue_cards", 0) > 5:
        score -= 10 * weights["trello_overdue"]
    if trello_data.get("average_list_movement_time", 0) > 86400:  # 1 day
        score -= 5 * weights["trello_movement"]
    if trello_data.get("average_comment_count", 0) < 1:
        score -= 5 * weights["trello_comments"]

    # Git scoring
    commits_per_day = git_data.get("commits_per_day", {})
    avg_commits = sum(commits_per_day.values()) / len(commits_per_day) if commits_per_day else 0
    if avg_commits < 1:
        score -= 10 * weights["git_commits"]

    if git_data.get("pull_request_comments", 0) < 5: # Assuming a threshold for healthy discussion
        score -= 5 * weights["git_pr_comments"]

    if git_data.get("lines_of_code_changed", 0) < 100: # Low churn might indicate stagnation
        score -= 2 * weights["git_code_churn"]

    # Slack scoring
    if slack_data.get("average_sentiment", 0) < -0.05: # Threshold for negative sentiment
        score -= 15 * weights["slack_sentiment"]
    elif slack_data.get("average_sentiment", 0) < 0.2: # Threshold for neutral/low sentiment
        score -= 5 * weights["slack_sentiment"]

    # Google Calendar scoring
    if google_calendar_data.get("number_of_meetings", 0) > 15: # High number of meetings
        score -= 5 * weights["gcal_meeting_count"]

    total_meeting_hours = google_calendar_data.get("total_meeting_length", 0) / 3600
    if total_meeting_hours > 20: # More than 20 hours of meetings in the upcoming period
        score -= 10 * weights["gcal_meeting_length"]

    return max(0, int(score))
