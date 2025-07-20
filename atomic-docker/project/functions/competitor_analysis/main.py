from fastapi import FastAPI
from competitor_analysis import generate_competitor_briefing
from notion_integration import create_notion_page

app = FastAPI()

@app.post("/competitor-analysis")
def competitor_analysis(competitor_website: str, competitor_twitter_username: str, competitor_name: str, competitor_ticker: str):
    """
    Generates a competitor briefing and creates a new page in Notion with the briefing.
    """
    competitor_briefing = generate_competitor_briefing(competitor_website, competitor_twitter_username, competitor_name, competitor_ticker)

    create_notion_page(f"Competitor Briefing for {competitor_name}", competitor_briefing)

    return {"status": "success"}
