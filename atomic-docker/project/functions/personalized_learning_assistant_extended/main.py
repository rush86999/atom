from fastapi import FastAPI, Depends, HTTPException
from .dependencies import (
    get_get_coursera_data,
    get_get_udemy_data,
    get_get_edx_data,
    get_get_pocket_data,
    get_get_instapaper_data,
    get_get_notion_data,
    get_create_user_profile,
    get_get_recommendations,
    get_schedule_learning_sessions,
)

app = FastAPI()

@app.post("/personalized-learning-plan")
def personalized_learning_plan(
    coursera_user_id: str,
    udemy_user_id: str,
    edx_user_id: str,
    google_calendar_id: str,
    notion_database_id: str,
    learning_duration_minutes: int,
    get_coursera_data: callable = Depends(get_get_coursera_data),
    get_udemy_data: callable = Depends(get_get_udemy_data),
    get_edx_data: callable = Depends(get_get_edx_data),
    get_pocket_data: callable = Depends(get_get_pocket_data),
    get_instapaper_data: callable = Depends(get_get_instapaper_data),
    get_notion_data: callable = Depends(get_get_notion_data),
    create_user_profile: callable = Depends(get_create_user_profile),
    get_recommendations: callable = Depends(get_get_recommendations),
    schedule_learning_sessions: callable = Depends(get_schedule_learning_sessions),
):
    """
    Generates a personalized learning plan for the user.
    """
    try:
        coursera_data = get_coursera_data(coursera_user_id)
        udemy_data = get_udemy_data(udemy_user_id)
        edx_data = get_edx_data(edx_user_id)
        pocket_data = get_pocket_data()
        instapaper_data = get_instapaper_data()
        notion_data = get_notion_data(notion_database_id)

        user_profile = create_user_profile(
            coursera_data,
            udemy_data,
            edx_data,
            pocket_data,
            instapaper_data,
            notion_data,
        )

        recommendations = get_recommendations(user_profile)

        schedule_learning_sessions(
            google_calendar_id,
            recommendations,
            learning_duration_minutes,
        )

        return {"status": "success", "recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
