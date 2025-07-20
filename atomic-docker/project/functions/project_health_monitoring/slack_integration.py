import os
from slack_sdk import WebClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def get_slack_data(channel_id):
    """
    Fetches data from a Slack channel and performs sentiment analysis.

    Args:
        channel_id: The ID of the Slack channel.

    Returns:
        A dictionary containing the Slack data.
    """
    api_key = os.environ.get("SLACK_API_KEY")

    if not api_key:
        raise Exception("SLACK_API_KEY environment variable is not set.")

    client = WebClient(token=api_key)
    analyzer = SentimentIntensityAnalyzer()

    response = client.conversations_history(channel=channel_id)
    messages = response["messages"]

    sentiment_scores = []
    for message in messages:
        sentiment_scores.append(analyzer.polarity_scores(message["text"])["compound"])

    return {
        "average_sentiment": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    }
