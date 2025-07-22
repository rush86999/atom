import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import Dict, Any, List

class SlackManager:
    """A manager for interacting with the Slack API."""

    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self.analyzer = SentimentIntensityAnalyzer()

    def get_channel_history(self, channel_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetches conversation history from a Slack channel."""
        try:
            result = self.client.conversations_history(channel=channel_id, limit=limit)
            return result.get("messages", [])
        except SlackApiError as e:
            print(f"Error fetching conversation history from Slack: {e.response['error']}")
            return []

    def calculate_average_sentiment(self, messages: List[Dict[str, Any]]) -> float:
        """Calculates the average sentiment score of a list of messages."""
        sentiment_scores = [
            self.analyzer.polarity_scores(message["text"])["compound"]
            for message in messages if "text" in message
        ]
        return sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

def get_slack_data(channel_id: str) -> Dict[str, Any]:
    """
    Fetches and processes data from a Slack channel to assess team morale.

    Args:
        channel_id: The ID of the Slack channel.

    Returns:
        A dictionary containing Slack data points for project health.
    """
    token = os.environ.get("SLACK_API_KEY")
    if not token:
        raise ValueError("SLACK_API_KEY environment variable must be set.")

    slack_manager = SlackManager(token)

    try:
        messages = slack_manager.get_channel_history(channel_id)
        if not messages:
            print(f"No messages found in channel {channel_id}.")
            return {"average_sentiment": 0}

        average_sentiment = slack_manager.calculate_average_sentiment(messages)

        return {"average_sentiment": average_sentiment}
    except Exception as e:
        print(f"An unexpected error occurred while processing Slack data: {e}")
        # Return a default/error structure
        return {"average_sentiment": 0, "error": str(e)}
