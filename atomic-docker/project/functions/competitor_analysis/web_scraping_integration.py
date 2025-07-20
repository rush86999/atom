import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    """
    Scrapes a website for new blog posts, press releases, and product updates.

    Args:
        url: The URL of the website to scrape.

    Returns:
        A dictionary containing the scraped data.
    """
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    blog_posts = []
    for post in soup.find_all("article", class_="blog-post"):
        title = post.find("h2").text
        link = post.find("a")["href"]
        blog_posts.append({"title": title, "link": link})

    press_releases = []
    for release in soup.find_all("div", class_="press-release"):
        title = release.find("h3").text
        link = release.find("a")["href"]
        press_releases.append({"title": title, "link": link})

    product_updates = []
    for update in soup.find_all("div", class_="product-update"):
        title = update.find("h4").text
        link = update.find("a")["href"]
        product_updates.append({"title": title, "link": link})

    return {
        "blog_posts": blog_posts,
        "press_releases": press_releases,
        "product_updates": product_updates,
    }
