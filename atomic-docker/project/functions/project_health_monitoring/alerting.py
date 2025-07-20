import os
import smtplib

def send_alert(project_manager_email, project_health_score):
    """
    Sends an alert to the project manager.

    Args:
        project_manager_email: The email address of the project manager.
        project_health_score: The project health score.
    """
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        raise Exception("SENDER_EMAIL and SENDER_PASSWORD environment variables are not set.")

    message = f"""\
Subject: Project Health Alert

The health score for your project has dropped to {project_health_score}.
"""

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, project_manager_email, message)
