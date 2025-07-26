import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Attempt to import the actual 'tweepy' library.
# If it fails, this script defines mock classes to allow the application
# to run for local development or testing without the dependency.
try:
    import tweepy
    logging.info("Successfully imported 'tweepy' library.")
except ImportError:
    # --- MOCK IMPLEMENTATIONS ---
    # This block is executed if 'tweepy' is not installed.
    # We define mock classes to simulate tweepy's behavior.
    logging.info("Tweepy library not found. Using mock implementation.")

    class MockUser:
        """Mocks the User object in tweepy."""
        def __init__(self, screen_name="mock_user", user_id="12345"):
            self.id_str = user_id
            self.screen_name = screen_name
            self.name = "Mock User"
            self.followers_count = 150
            self.friends_count = 75
            self._json = {
                "id_str": self.id_str,
                "screen_name": self.screen_name,
                "name": self.name,
                "followers_count": self.followers_count,
                "friends_count": self.friends_count,
            }

    class MockTweet:
        """Mocks the Status (Tweet) object in tweepy."""
        def __init__(self, id_str="98765", text="This is a mock tweet.", user=None):
            self.id_str = id_str
            self.text = text
            self.created_at = datetime.utcnow()
            self.user = user or MockUser()
            self.retweet_count = 10
            self.favorite_count = 25
            self.retweeted = False
            self.favorited = False
            # The `_json` attribute is a common pattern for holding the raw data.
            self._json = {
                "id_str": self.id_str,
                "text": self.text,
                "created_at": self.created_at.strftime('%a %b %d %H:%M:%S +0000 %Y'),
                "user": self.user._json,
                "retweet_count": self.retweet_count,
                "favorite_count": self.favorite_count,
                "retweeted": self.retweeted,
                "favorited": self.favorited,
            }

    class MockCursor:
        """Mocks the Cursor object for paginating results."""
        def __init__(self, api_method, *args, **kwargs):
            self._method = api_method
            self._args = args
            self._kwargs = kwargs

        def items(self, limit=20):
            """Returns a generator of mock items."""
            for i in range(limit):
                yield MockTweet(id_str=f"mock_item_{i}")

        def pages(self, limit=1):
             """Returns a generator of mock pages (lists of items)."""
             for i in range(limit):
                 yield [MockTweet(id_str=f"mock_page_{i}_item_{j}") for j in range(5)]


    class MockAPI:
        """Mocks the API class in tweepy."""
        def __init__(self, auth=None):
            self.auth = auth

        def verify_credentials(self):
            logging.info("Mock verify_credentials called.")
            return MockUser()

        def home_timeline(self, count=20, **kwargs):
            return [MockTweet(id_str=f"home_{i}") for i in range(min(count, 5))]

        def user_timeline(self, user_id=None, screen_name=None, count=20, **kwargs):
            return [MockTweet(id_str=f"user_{i}") for i in range(min(count, 5))]

        def get_status(self, id, **kwargs):
            return MockTweet(id_str=str(id))

        def mentions_timeline(self, count=20, **kwargs):
            return [MockTweet(id_str=f"mention_{i}") for i in range(min(count, 5))]

        def update_status(self, status, **kwargs):
            return MockTweet(text=status)

        def destroy_status(self, id):
            return MockTweet(id_str=str(id))

        def retweet(self, id):
            return MockTweet(id_str=str(id))

        def create_favorite(self, id):
            return MockTweet(id_str=str(id))

        def search_tweets(self, q, count=15, **kwargs):
            """Mock search_tweets method for compatibility with tweepy v4+."""
            return [MockTweet(id_str=f"search_{i}", text=f"Tweet about {q}") for i in range(min(count, 5))]

    class MockOAuth1UserHandler:
        """Mocks the OAuth1UserHandler for authentication."""
        def __init__(self, consumer_key, consumer_secret, access_token=None, access_token_secret=None):
            self.consumer_key = consumer_key
            self.consumer_secret = consumer_secret
            self.access_token = access_token
            self.access_token_secret = access_token_secret

        def set_access_token(self, key, secret):
            self.access_token = key
            self.access_token_secret = secret

    class MockTweepyModule:
        """
        A mock object that mimics the structure of the imported 'tweepy' module.
        It holds the mock classes as attributes so the rest of the application
        can use it transparently (e.g., `tweepy.API`, `tweepy.Cursor`).
        """
        API = MockAPI
        OAuth1UserHandler = MockOAuth1UserHandler
        Cursor = MockCursor
        # Define mock exceptions
        TweepyException = type('TweepyException', (Exception,), {})
        RateLimitError = type('RateLimitError', (TweepyException,), {})


    # Assign the mock module to the 'tweepy' name.
    # The rest of the file can now use 'tweepy' as if it were the real library.
    tweepy = MockTweepyModule()


logger = logging.getLogger(__name__)

async def get_twitter_api(user_id: str, db_conn_pool) -> Optional['tweepy.API']:
    """
    Constructs and returns a Tweepy API object for a given user.

    In a real application, this function would securely fetch the user's OAuth
    credentials from a database. For this example, it retrieves them from
    environment variables. This is NOT secure for production.
    """
    # NOTE: This implementation is a placeholder. A real-world application must
    # implement a full OAuth flow and securely store/retrieve user tokens.
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET", "")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        logger.error("Twitter API credentials are not fully configured in environment variables.")
        return None

    try:
        auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
        api = tweepy.API(auth)
        # Verify that the credentials are valid
        api.verify_credentials()
        return api
    except tweepy.TweepyException as e:
        logger.error(f"Failed to create Twitter API client for user {user_id}: {e}", exc_info=True)
        return None


async def get_timeline(api: 'tweepy.API', count: int = 20) -> List[Dict[str, Any]]:
    """Fetches the user's home timeline."""
    try:
        timeline = api.home_timeline(count=count)
        return [t._json for t in timeline]
    except Exception as e:
        logger.error(f"Error fetching Twitter timeline: {e}")
        return []


async def post_tweet(api: 'tweepy.API', status: str) -> Optional[Dict[str, Any]]:
    """Posts a new tweet."""
    if not status:
        logger.error("Cannot post an empty tweet.")
        return None
    try:
        tweet = api.update_status(status)
        return tweet._json
    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        return None


async def search_tweets(api: 'tweepy.API', query: str, count: int = 15) -> List[Dict[str, Any]]:
    """Searches for recent tweets matching a query."""
    try:
        # Note: The attribute for accessing search results in tweepy v1 is just iterating the result.
        # In v2 it's different. Assuming v1 based on other function calls.
        tweets = api.search_tweets(q=query, count=count)
        return [t._json for t in tweets]
    except Exception as e:
        logger.error(f"Error searching tweets for query '{query}': {e}")
        return []


async def get_tweet(api: 'tweepy.API', tweet_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single tweet by its ID."""
    try:
        tweet = api.get_status(tweet_id, tweet_mode="extended")
        return tweet._json
    except Exception as e:
        logger.error(f"Error getting tweet {tweet_id}: {e}")
        return None
