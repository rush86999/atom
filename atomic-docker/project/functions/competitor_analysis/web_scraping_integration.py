import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    """
    Scrapes a website for blog posts, press releases, and product updates.

    Args:
        url: The URL of the website to scrape.

    Returns:
        A dictionary containing the scraped data.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error scraping website: {e}")
        return {
            "blog_posts": [],
            "press_releases": [],
            "product_updates": [],
        }

    soup = BeautifulSoup(response.content, "html.parser")

    blog_posts = []
    for post in soup.find_all("a", href=lambda href: href and "/blog/" in href):
        blog_posts.append({
            "title": post.text.strip(),
            "link": post["href"],
        })

    press_releases = []
    for release in soup.find_all("a", href=lambda href: href and "/press/" in href):
        press_releases.append({
            "title": release.text.strip(),
            "link": release["href"],
        })

    product_updates = []
    for update in soup.find_all("a", href=lambda href: href and "/product-updates/" in href):
        product_updates.append({
            "title": update.text.strip(),
            "link": update["href"],
        })

    return {
        "blog_posts": blog_posts,
        "press_releases": press_releases,
        "product_updates": product_updates,
    }
