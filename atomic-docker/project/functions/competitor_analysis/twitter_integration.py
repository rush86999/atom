import os
import tweepy

def get_twitter_data(username):
    """
    Fetches data from a Twitter user's profile.

    Args:
        username: The username of the Twitter user.

    Returns:
        A dictionary containing the Twitter data.
    """
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not consumer_key or not consumer_secret or not access_token or not access_token_secret:
        raise Exception("Twitter API keys are not set.")

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth)

    tweets = api.user_timeline(screen_name=username, count=10)

    return {
        "tweets": [tweet.text for tweet in tweets]
    }
