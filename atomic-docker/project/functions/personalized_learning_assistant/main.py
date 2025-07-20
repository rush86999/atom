from fastapi import FastAPI
from personalized_learning_assistant import generate_personalized_learning_plan

app = FastAPI()

@app.post("/personalized-learning-plan")
def personalized_learning_plan(coursera_user_id: str, udemy_user_id: str, edx_user_id: str, pocket_consumer_key: str, pocket_access_token: str, instapaper_consumer_key: str, instapaper_consumer_secret: str, instapaper_oauth_token: str, instapaper_oauth_token_secret: str, google_calendar_id: str, notion_database_id: str):
    """
    Generates a personalized learning plan.
    """
    personalized_learning_plan = generate_personalized_learning_plan(coursera_user_id, udemy_user_id, edx_user_id, pocket_consumer_key, pocket_access_token, instapaper_consumer_key, instapaper_consumer_secret, instapaper_oauth_token, instapaper_oauth_token_secret, google_calendar_id, notion_database_id)

    return personalized_learning_plan
