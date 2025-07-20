import os
import tweepy

def get_twitter_data(username):
    """
    Gets a user's recent tweets.

    Args:
        username: The Twitter username of the user.

    Returns:
        A dictionary containing the user's recent tweets.
    """
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("Twitter API keys are not set.")
        return {"tweets": []}

    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    try:
        tweets = api.user_timeline(screen_name=username, count=10, tweet_mode="extended")
    except tweepy.errors.TweepyException as e:
        print(f"Error getting tweets: {e}")
        return {"tweets": []}

    return {"tweets": [tweet.full_text for tweet in tweets]}
