from apscheduler.schedulers.background import BackgroundScheduler
from main import project_health
from database import get_db_connection

def start_scheduler():
    """
    Starts the scheduler.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(project_health, "interval", minutes=60)
    scheduler.start()
