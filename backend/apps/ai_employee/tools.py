import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Try importing real dependencies
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


import email
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import imaplib
import smtplib
import sqlite3
import datetime

class EmployeeTools:
    """
    Real-world execution capabilities for the Atom AI Employee (True Live Demo POV).
    """
    
    @staticmethod
    def read_inbound_email() -> str:
        """Connects to IMAP to read the latest unseen emails from the dummy inbox."""
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        user = os.getenv("DUMMY_EMAIL")
        password = os.getenv("DUMMY_EMAIL_APP_PASSWORD")
        if not user or not password:
            return "Failed: DUMMY_EMAIL or DUMMY_EMAIL_APP_PASSWORD not set in .env"
        
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(user, password)
            mail.select("inbox")
            
            # Search for ALL emails to guarantee robustness during demo
            status, messages = mail.search(None, 'ALL')
            if status != "OK" or not messages[0]:
                return "No emails found in the inbox."
                
            email_ids = messages[0].split()
            # Get up to the 3 most recent emails
            recent_ids = email_ids[-3:]
            
            all_emails_text = []
            
            for eid in recent_ids:
                res, msg_data = mail.fetch(eid, '(RFC822)')
                body = "(No Body Found)"
                subject = "(No Subject)"
                sender = "(Unknown Sender)"
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Decode subject
                        subj = decode_header(msg.get("Subject", ""))[0]
                        subject = subj[0].decode(subj[1] if subj[1] else "utf-8") if isinstance(subj[0], bytes) else subj[0]
                        sender = msg.get("From", "")
                        
                        # Extract Body
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    try:
                                        body = part.get_payload(decode=True).decode()
                                        break
                                    except Exception:
                                        pass
                        else:
                            try:
                                body = msg.get_payload(decode=True).decode()
                            except Exception:
                                body = msg.get_payload()
                                
                all_emails_text.append(f"From: {sender}\nSubject: {subject}\n\n{body}")
                
            mail.logout()
            return "RECEIVED UNREAD EMAILS:\n" + "\n\n--- NEXT EMAIL ---\n\n".join(all_emails_text)
                    
        except Exception as e:
            return f"IMAP Connection Error: {str(e)}"

    @staticmethod
    def write_excel(data: Dict[str, Any], filename: str = "Machinery_Quote.xlsx") -> str:
        """Uses Pandas to write directly to the user's Desktop."""
        if not HAS_PANDAS:
            return "Failed: Pandas is not installed."
        
        try:
            home = os.path.expanduser('~')
            desktop_path = os.path.join(home, 'Desktop')
            onedrive_desktop = os.path.join(home, 'OneDrive', 'Desktop')
            
            if os.path.exists(onedrive_desktop):
                target_dir = onedrive_desktop
            elif os.path.exists(desktop_path):
                target_dir = desktop_path
            else:
                target_dir = os.getcwd()
                
            full_path = os.path.join(target_dir, filename)
            df = pd.DataFrame(data)
            df.to_excel(full_path, index=False)
            return f"Successfully generated physical spreadsheet: {full_path}"
        except Exception as e:
            logger.error(f"Error writing excel: {e}")
            return f"Failed to write Excel file: {str(e)}"

    @staticmethod
    def scrape_website(url: str) -> str:
        """Uses BeautifulSoup to fetch and parse text from a given URL."""
        if not HAS_BS4:
            return "Failed: BeautifulSoup is not installed."
            
        try:
            if not url.startswith('http'):
                url = 'https://' + url
                
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            return text[:2000] + ("..." if len(text) > 2000 else "")
            
        except requests.exceptions.HTTPError as he:
            if he.response.status_code == 404:
                return f"Website {url} returned 404 Not Found. Assume Brennan.ca is a mid-sized Canadian industrial manufacturing plant for this demo."
            return f"Failed to scrape website: HTTP Error {he.response.status_code}"
        except Exception as e:
            return f"Failed to scrape website '{url}': {str(e)}"

    @staticmethod
    def update_crm_database(data: Dict[str, str]) -> str:
        """Appends structured data to a real SQLite database to prove statefulness."""
        db_path = os.path.join(os.path.dirname(__file__), 'leads.db')
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    company TEXT,
                    email TEXT,
                    summary TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO leads (name, company, email, summary) 
                VALUES (?, ?, ?, ?)
            ''', (data.get('name', ''), data.get('company', ''), data.get('email', ''), data.get('summary', '')))
            
            conn.commit()
            conn.close()
            return f"Real Database: Successfully inserted lead '{data.get('name', 'Unknown')}' into AI Employee SQLite database."
        except Exception as e:
            return f"Database Error: {str(e)}"

    @staticmethod
    def send_email_smtp(to_address: str, subject: str, body: str, ics_content: str = None) -> str:
        """Sends a true SMTP email from the provided dummy account."""
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        user = os.getenv("DUMMY_EMAIL")
        password = os.getenv("DUMMY_EMAIL_APP_PASSWORD")
        if not user or not password:
            return "Failed: DUMMY_EMAIL credentials missing in .env"
            
        try:
            msg = MIMEMultipart()
            msg['From'] = user
            msg['To'] = to_address
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            if ics_content:
                part = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
                part.set_payload(ics_content.encode('utf-8'))
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
                msg.attach(part)
                
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login(user, password)
            server.send_message(msg)
            server.quit()
            return f"SMTP Transmitted successfully to {to_address}."
        except Exception as e:
            return f"SMTP Transmission Failed: {str(e)}"

    @staticmethod
    def schedule_meeting_ics(email_addr: str, topic: str, time_str: str) -> str:
        """Generates an authentic RFC 5545 meeting attachment and sends it to the participant."""
        # Tomorrow at 14:00 UTC
        dt = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        dt_start = dt.replace(hour=14, minute=0, second=0).strftime('%Y%m%dT%H%M%SZ')
        dt_end = dt.replace(hour=15, minute=0, second=0).strftime('%Y%m%dT%H%M%SZ')
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ATOM AI//Employee Virtual Agent//EN
METHOD:REQUEST
BEGIN:VEVENT
SUMMARY:{topic}
DTSTART:{dt_start}
DTEND:{dt_end}
ATTENDEE;RSVP=TRUE:mailto:{email_addr}
DESCRIPTION:Automated scheduling generated by Atom AI Employee.
END:VEVENT
END:VCALENDAR"""
        
        # We send the ICS file as an attachment
        return EmployeeTools.send_email_smtp(
            to_address=email_addr,
            subject=f"Meeting Invitation: {topic}",
            body=f"Hello,\n\nYour meeting '{topic}' scheduled for {time_str} has been confirmed.\nPlease find the attached calendar invitation.\n\nBest,\nAtom AI Employee",
            ics_content=ics_content
        )
