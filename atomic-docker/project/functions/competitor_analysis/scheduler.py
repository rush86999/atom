from apscheduler.schedulers.background import BackgroundScheduler
from main import competitor_analysis, weekly_briefing

def start_scheduler():
    """
    Starts the scheduler.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(competitor_analysis, "interval", hours=24)
    scheduler.add_job(weekly_briefing, "cron", day_of_week="mon", hour=9)
    scheduler.start()
