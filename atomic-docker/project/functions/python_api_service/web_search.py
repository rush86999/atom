import os
import logging
import requests

logger = logging.getLogger(__name__)

def search_web(query: str) -> str:
    """
    Searches the web for the given query using the DuckDuckGo Instant Answer API.
    """
    try:
        response = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json")
        response.raise_for_status()
        data = response.json()

        if data.get("AbstractText"):
            return data["AbstractText"]
        elif data.get("RelatedTopics"):
            results = ""
            for topic in data["RelatedTopics"]:
                if topic.get("Text"):
                    results += f"- {topic['Text']}\n"
            return results if results else "No results found."
        else:
            return "No results found."
    except Exception as e:
        logger.error(f"Error searching web: {e}")
        return "Error searching web."
