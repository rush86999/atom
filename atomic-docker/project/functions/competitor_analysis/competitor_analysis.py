from web_scraping_integration import scrape_website
from twitter_integration import get_twitter_data
from news_api_integration import get_news_data
from financial_data_integration import get_financial_data

def generate_competitor_briefing(competitor_website, competitor_twitter_username, competitor_name, competitor_ticker):
    """
    Generates a competitor briefing.

    Args:
        competitor_website: The website of the competitor.
        competitor_twitter_username: The Twitter username of the competitor.
        competitor_name: The name of the competitor.
        competitor_ticker: The ticker symbol of the competitor.

    Returns:
        A string containing the competitor briefing.
    """
    scraped_data = scrape_website(competitor_website)
    twitter_data = get_twitter_data(competitor_twitter_username)
    news_data = get_news_data(competitor_name)
    financial_data = get_financial_data(competitor_ticker)

    briefing = f"# Competitor Briefing for {competitor_name}\n\n"

    briefing += "## Website\n\n"
    if scraped_data["blog_posts"]:
        briefing += "### Blog Posts\n\n"
        for post in scraped_data["blog_posts"]:
            briefing += f"- [{post['title']}]({post['link']})\n"
    if scraped_data["press_releases"]:
        briefing += "\n### Press Releases\n\n"
        for release in scraped_data["press_releases"]:
            briefing += f"- [{release['title']}]({release['link']})\n"
    if scraped_data["product_updates"]:
        briefing += "\n### Product Updates\n\n"
        for update in scraped_data["product_updates"]:
            briefing += f"- [{update['title']}]({update['link']})\n"

    briefing += "\n## Twitter\n\n"
    for tweet in twitter_data["tweets"]:
        briefing += f"- {tweet}\n"

    briefing += "\n## News\n\n"
    for article in news_data["articles"]:
        briefing += f"- [{article['title']}]({article['url']})\n"

    briefing += "\n## Financials\n\n"
    briefing += f"**Market Cap:** {financial_data['info']['marketCap']}\n"
    briefing += f"**Enterprise Value:** {financial_data['info']['enterpriseValue']}\n"
    briefing += f"**Trailing P/E:** {financial_data['info']['trailingPE']}\n"
    briefing += f"**Forward P/E:** {financial_data['info']['forwardPE']}\n"
    briefing += f"**PEG Ratio:** {financial_data['info']['pegRatio']}\n"

    return briefing
