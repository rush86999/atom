import json
import os
from datetime import datetime, timedelta

DATA_FILE = "competitor_data.json"

def store_data(competitor_name, scraped_data, twitter_data, news_data, financial_data):
    """
    Stores the competitor data in a JSON file.
    """
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)

    with open(DATA_FILE, "r+") as f:
        data = json.load(f)
        if competitor_name not in data:
            data[competitor_name] = []

        data[competitor_name].append({
            "timestamp": datetime.now().isoformat(),
            "scraped_data": scraped_data,
            "twitter_data": twitter_data,
            "news_data": news_data,
            "financial_data": financial_data,
        })
        f.seek(0)
        json.dump(data, f, indent=4)

def generate_weekly_briefing():
    """
    Generates a weekly competitor briefing.
    """
    if not os.path.exists(DATA_FILE):
        return "No data available to generate a weekly briefing."

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    briefing = "# Weekly Competitor Briefing\n\n"
    one_week_ago = datetime.now() - timedelta(weeks=1)

    for competitor_name, entries in data.items():
        briefing += f"## {competitor_name}\n\n"

        weekly_blog_posts = []
        weekly_press_releases = []
        weekly_product_updates = []
        weekly_tweets = []
        weekly_articles = []

        for entry in entries:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time >= one_week_ago:
                weekly_blog_posts.extend(entry["scraped_data"]["blog_posts"])
                weekly_press_releases.extend(entry["scraped_data"]["press_releases"])
                weekly_product_updates.extend(entry["scraped_data"]["product_updates"])
                weekly_tweets.extend(entry["twitter_data"]["tweets"])
                weekly_articles.extend(entry["news_data"]["articles"])

        if weekly_blog_posts:
            briefing += "### Blog Posts\n\n"
            for post in weekly_blog_posts:
                briefing += f"- [{post['title']}]({post['link']})\n"

        if weekly_press_releases:
            briefing += "\n### Press Releases\n\n"
            for release in weekly_press_releases:
                briefing += f"- [{release['title']}]({release['link']})\n"

        if weekly_product_updates:
            briefing += "\n### Product Updates\n\n"
            for update in weekly_product_updates:
                briefing += f"- [{update['title']}]({update['link']})\n"

        if weekly_tweets:
            briefing += "\n## Twitter\n\n"
            for tweet in weekly_tweets:
                briefing += f"- {tweet}\n"

        if weekly_articles:
            briefing += "\n## News\n\n"
            for article in weekly_articles:
                briefing += f"- [{article['title']}]({article['url']})\n"

    return briefing
