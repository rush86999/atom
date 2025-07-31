from fastapi import FastAPI, Depends, HTTPException
from competitor_analysis.competitor_analysis import generate_competitor_briefing
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

from database import get_db_connection

@app.post("/competitors")
def create_competitor(name: str, website: str, twitter_username: str = None, ticker: str = None):
    """
    Creates a new competitor configuration.
    """
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO competitors (name, website, twitter_username, ticker) VALUES (?, ?, ?, ?)",
        (name, website, twitter_username, ticker),
    )
    conn.commit()
    conn.close()
    return {"message": "Competitor created successfully."}

@app.get("/competitors")
def get_competitors():
    """
    Returns all competitor configurations.
    """
    conn = get_db_connection()
    competitors = conn.execute("SELECT * FROM competitors").fetchall()
    conn.close()
    return competitors

@app.put("/competitors/{competitor_id}")
def update_competitor(competitor_id: int, name: str, website: str, twitter_username: str = None, ticker: str = None):
    """
    Updates a competitor configuration.
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE competitors SET name = ?, website = ?, twitter_username = ?, ticker = ? WHERE id = ?",
        (name, website, twitter_username, ticker, competitor_id),
    )
    conn.commit()
    conn.close()
    return {"message": "Competitor updated successfully."}

@app.delete("/competitors/{competitor_id}")
def delete_competitor(competitor_id: int):
    """
    Deletes a competitor configuration.
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM competitors WHERE id = ?", (competitor_id,))
    conn.commit()
    conn.close()
    return {"message": "Competitor deleted successfully."}

def competitor_analysis():
    """
    Generates a competitor briefing for each competitor in the database.
    """
    conn = get_db_connection()
    competitors = conn.execute("SELECT * FROM competitors").fetchall()
    conn.close()

    for competitor in competitors:
        try:
            scraped_data = scrape_website(competitor["website"])
            twitter_data = get_twitter_data(competitor["twitter_username"])
            news_data = get_news_data(competitor["name"])
            financial_data = get_financial_data(competitor["ticker"])

            store_data(competitor["name"], scraped_data, twitter_data, news_data, financial_data)

            competitor_briefing = generate_competitor_briefing(
                competitor["name"],
                scraped_data,
                twitter_data,
                news_data,
                financial_data
            )

            create_notion_page(f"Competitor Briefing for {competitor['name']}", competitor_briefing)
        except Exception as e:
            print(f"Error generating competitor briefing for {competitor['name']}: {e}")

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
