import subprocess

def install_dependencies():
    """
    Installs the required dependencies for the competitor analysis feature.
    """
    dependencies = [
        "fastapi",
        "uvicorn",
        "requests",
        "beautifulsoup4",
        "tweepy",
        "newsapi-python",
        "yfinance",
        "notion-client",
    ]
    for dependency in dependencies:
        subprocess.run(["pip", "install", dependency])

install_dependencies()

from web_scraping_integration import scrape_website
from twitter_integration import get_twitter_data
from news_api_integration import get_news_data
from financial_data_integration import get_financial_data
from notion_integration import create_notion_page
from weekly_briefing import store_data, generate_weekly_briefing

def get_scrape_website():
    return scrape_website

def get_get_twitter_data():
    return get_twitter_data

def get_get_news_data():
    return get_news_data

def get_get_financial_data():
    return get_financial_data

def get_create_notion_page():
    return create_notion_page

def get_store_data():
    return store_data

def get_generate_weekly_briefing():
    return generate_weekly_briefing
