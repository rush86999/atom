from fastapi import FastAPI, Depends, HTTPException
from competitor_analysis import generate_competitor_briefing
from dependencies import (
    install_dependencies,
    get_scrape_website,
    get_get_twitter_data,
    get_get_news_data,
    get_get_financial_data,
    get_create_notion_page,
    get_store_data,
    get_generate_weekly_briefing,
)

install_dependencies()

app = FastAPI()

@app.post("/competitor-analysis")
def competitor_analysis(
    competitor_website: str,
    competitor_twitter_username: str,
    competitor_name: str,
    competitor_ticker: str,
    scrape_website: callable = Depends(get_scrape_website),
    get_twitter_data: callable = Depends(get_get_twitter_data),
    get_news_data: callable = Depends(get_get_news_data),
    get_financial_data: callable = Depends(get_get_financial_data),
    create_notion_page: callable = Depends(get_create_notion_page),
    store_data: callable = Depends(get_store_data),
):
    """
    Generates a competitor briefing and creates a new page in Notion with the briefing.
    """
    try:
        scraped_data = scrape_website(competitor_website)
        twitter_data = get_twitter_data(competitor_twitter_username)
        news_data = get_news_data(competitor_name)
        financial_data = get_financial_data(competitor_ticker)

        store_data(competitor_name, scraped_data, twitter_data, news_data, financial_data)

        competitor_briefing = generate_competitor_briefing(
            competitor_name,
            scraped_data,
            twitter_data,
            news_data,
            financial_data
        )

        create_notion_page(f"Competitor Briefing for {competitor_name}", competitor_briefing)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/weekly-briefing")
def weekly_briefing(
    generate_weekly_briefing: callable = Depends(get_generate_weekly_briefing),
    create_notion_page: callable = Depends(get_create_notion_page),
):
    """
    Generates a weekly competitor briefing and creates a new page in Notion with the briefing.
    """
    try:
        briefing = generate_weekly_briefing()
        create_notion_page("Weekly Competitor Briefing", briefing)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
