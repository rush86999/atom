from .celery_app import app
import httpx
from celery import group

SERVICE_URLS = {
    'dropbox': 'http://dropbox-api:5001',
    # Add other services here
}

@app.task
def execute_http_request(method, url, json_data):
    with httpx.Client() as client:
        response = client.request(method, url, json=json_data)
        return response.status_code, response.json()

@app.task
def check_budget_alerts():
    from project.database import SessionLocal
    from project import models
    from datetime import datetime

    db = SessionLocal()
    try:
        users = db.query(models.User).all()
        for user in users:
            budgets = db.query(models.Budget).filter(models.Budget.user_id == user.id, models.Budget.is_active == True).all()
            for budget in budgets:
                start_date = budget.start_date
                end_date = budget.end_date or datetime.now().date()
                transactions = db.query(models.Transaction).filter(
                    models.Transaction.account.has(user_id=user.id),
                    models.Transaction.date >= start_date,
                    models.Transaction.date <= end_date,
                    models.Transaction.category == budget.category
                ).all()

                spending = sum(t.amount for t in transactions)
                spending_percentage = (spending / budget.amount) * 100

                alert_settings = db.query(models.BudgetAlertSettings).filter(models.BudgetAlertSettings.user_id == user.id).first()
                if not alert_settings or not alert_settings.is_enabled:
                    continue

                if spending_percentage >= alert_settings.threshold:
                    # Send email alert
                    print(f"User {user.id} has exceeded {alert_settings.threshold}% of their {budget.name} budget.")
                    subject = f"Budget Alert: Approaching limit for {budget.name}"
                    text = f"You have spent {spending:.2f} of your {budget.amount:.2f} budget for {budget.name} ({spending_percentage:.0f}%)."
                    if spending_percentage >= 100:
                        subject = f"Budget Alert: Exceeded limit for {budget.name}"
                        text = f"You have exceeded your {budget.amount:.2f} budget for {budget.name}. You have spent {spending:.2f} ({spending_percentage:.0f}%)."

                    json_data = {
                        "to": user.email,
                        "subject": subject,
                        "text": text
                    }
                    execute_http_request.delay('POST', 'http://gmail-service:3000/send-email', json_data)
    finally:
        db.close()

@app.task
def execute_workflow(workflow):
    nodes = workflow['definition']['nodes']
    edges = workflow['definition']['edges']

    # For simplicity, we will still execute all actions in parallel for now.
    # A full implementation would traverse the graph.

    tasks = []
    for node in nodes:
        if node['type'] == 'genericNode':
            service = node['data']['service']
            # e.g., 'Save File' -> 'save-file'
            action_name = node['data']['name'].lower().replace(' ', '-')

            if service in SERVICE_URLS:
                url = f"{SERVICE_URLS[service]}/{action_name}"
                method = 'POST' # Assuming all actions are POST for now
                params = node['data']['values']
                tasks.append(execute_http_request.s(method, url, params))

    if tasks:
        task_group = group(tasks)
        result = task_group.apply_async()
        return result.id

    return None
