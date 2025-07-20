import os
from newsapi import NewsApiClient

def get_news_data(query):
    """
    Gets recent news articles about a query.

    Args:
        query: The query to search for.

    Returns:
        A dictionary containing the recent news articles.
    """
    api_key = os.environ.get("NEWS_API_KEY")

    if not api_key:
        print("News API key is not set.")
        return {"articles": []}

    newsapi = NewsApiClient(api_key=api_key)

    try:
        all_articles = newsapi.get_everything(q=query, language="en", sort_by="relevancy", page_size=10)
    except Exception as e:
        print(f"Error getting news articles: {e}")
        return {"articles": []}

    return {"articles": all_articles["articles"]}
