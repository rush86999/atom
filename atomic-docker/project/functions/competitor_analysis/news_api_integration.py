import os
from newsapi import NewsApiClient

def get_news_data(query):
    """
    Fetches news articles related to a query.

    Args:
        query: The query to search for.

    Returns:
        A dictionary containing the news data.
    """
    api_key = os.environ.get("NEWS_API_KEY")

    if not api_key:
        raise Exception("NEWS_API_KEY environment variable is not set.")

    newsapi = NewsApiClient(api_key=api_key)

    all_articles = newsapi.get_everything(q=query, language="en", sort_by="publishedAt", page_size=10)

    return {
        "articles": all_articles["articles"]
    }
