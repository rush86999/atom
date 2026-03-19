import io
import os
import sys
import time
import socket
import shutil
import subprocess

# Fix Windows cp1252 encoding
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DEBUG_PORT      = 9224
AUTH_TIMEOUT    = 120   # seconds to wait for you to log in manually
ELEMENT_TIMEOUT = 30

# Google Sheets — paste the full URL of your sheet here
# e.g. "https://docs.google.com/spreadsheets/d/XXXX/edit"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/14HcGbkrDpCTcvoParYHWCmT1Y-p4Q1Gz7m2QzdHqdx0/edit?usp=sharing"

# Discord — paste your webhook URL here
# e.g. "https://discord.com/api/webhooks/123456/abcdef"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1482211219187437750/LNBwNAIWiT4IXJvZLeWOL2uEw3Rspvt7YBfm3kKB9ha6jJ4bWQhWz_ZzYydVHWAXT2N8"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def log(msg):  print(f"[+] {msg}", flush=True)
def warn(msg): print(f"[!] {msg}", flush=True)
def err(msg):  print(f"[ERROR] {msg}", flush=True)


def find_chrome():
    for path in [
        os.path.join(os.environ.get("ProgramFiles",       ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)",  ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA",       ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError("Chrome not found.")


def kill_chrome():
    log("Killing Chrome and chromedriver ...")
    for _ in range(3):
        subprocess.run(["taskkill", "/f", "/im", "chrome.exe"],      capture_output=True)
        subprocess.run(["taskkill", "/f", "/im", "chromedriver.exe"], capture_output=True)
        time.sleep(1)
    for _ in range(15):
        r = subprocess.run('tasklist /fi "imagename eq chrome.exe" /fo csv /nh',
                           capture_output=True, shell=True, text=True)
        if "chrome.exe" not in r.stdout.lower():
            log("Chrome is dead.")
            return
        time.sleep(1)
    warn("Chrome may still be running.")


def clone_profile():
    local  = os.environ.get("LOCALAPPDATA", "")
    src    = os.path.join(local, "Google", "Chrome", "User Data")
    tmp    = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "chrome_demo_profile")

    log(f"Nuking old temp profile at {tmp} ...")
    shutil.rmtree(tmp, ignore_errors=True)
    time.sleep(1)

    dest_profile = os.path.join(tmp, "Default")
    os.makedirs(dest_profile, exist_ok=True)

    # Local State — needed for DPAPI cookie decryption
    ls_src = os.path.join(src, "Local State")
    if os.path.exists(ls_src):
        try:
            shutil.copy2(ls_src, os.path.join(tmp, "Local State"))
            log("Copied Local State.")
        except Exception as e:
            warn(f"Local State copy failed: {e}")

    for item in ["Cookies", "Preferences", "Network"]:
        s = os.path.join(src, "Default", item)
        d = os.path.join(dest_profile, item)
        if not os.path.exists(s):
            continue
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
            log(f"Copied {item}")
        except Exception as e:
            warn(f"Could not copy {item}: {e}")

    return tmp, "Default"


def launch_chrome(user_data_dir, profile_dir, chrome_exe):
    cmd = [
        chrome_exe,
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_dir}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--start-maximized",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "about:blank",
    ]
    log(f"Launching Chrome (port {DEBUG_PORT}) ...")
    subprocess.Popen(cmd)
    log("Waiting for debug port ...")
    for i in range(30):
        try:
            with socket.create_connection(("127.0.0.1", DEBUG_PORT), timeout=1):
                log(f"Port open after {i+1}s.")
                time.sleep(2)
                return
        except OSError:
            time.sleep(1)
    warn("Debug port never opened.")


def attach_selenium():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    svc    = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=svc, options=opts)
    log("Selenium attached.")
    return driver


def wait_for_url(driver, fragment, timeout=AUTH_TIMEOUT, label=""):
    log(f"Waiting for URL fragment '{fragment}' ({label}) ...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: fragment in d.current_url.lower()
        )
        log("URL matched.")
        time.sleep(2)
        return True
    except TimeoutException:
        err(f"Timed out waiting for '{fragment}'.")
        return False


def safe_click(driver, el):
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


def wait_and_find(driver, css, timeout=ELEMENT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, css))
    )


def new_tab(driver, url):
    driver.execute_script(f"window.open('{url}', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(3)


# ─────────────────────────────────────────────
# PHASE 1 — Gmail
# ─────────────────────────────────────────────

def phase_gmail(driver):
    log("--- PHASE 1: Gmail ---")
    driver.get("https://mail.google.com/mail/u/0/#inbox")
    time.sleep(3)

    if any(x in driver.current_url.lower() for x in ["accounts.google", "signin", "servicelogin"]):
        log("Please log in to Gmail in the browser ...")
        if not wait_for_url(driver, "mail.google.com", label="Gmail"):
            return ""

    log("Waiting for inbox to load ...")
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.zA"))
        )
    except TimeoutException:
        warn("Inbox rows not found.")
        return ""

    rows = driver.find_elements(By.CSS_SELECTOR, "tr.zA")
    if not rows:
        warn("No emails found.")
        return ""

    log(f"Found {len(rows)} emails. Finding first non-automated email ...")

    # Skip emails from automated/noreply senders
    skip_keywords = ["noreply", "no-reply", "donotreply", "discord", "google", 
                     "automated", "notification", "mailer", "support@", "verify"]
    
    target_row = None
    for row in rows[:10]:  # check first 10 only
        try:
            sender_el = row.find_element(By.CSS_SELECTOR, "span.yP, span[email]")
            sender = (sender_el.get_attribute("email") or sender_el.text).lower()
            if not any(skip in sender for skip in skip_keywords):
                log(f"Selected email from: {sender}")
                target_row = row
                break
        except Exception:
            continue

    # Fall back to first email if nothing passed the filter
    if target_row is None:
        warn("No non-automated email found, using first email anyway.")
        target_row = rows[0]

    driver.execute_script("arguments[0].style.outline='3px solid red'", target_row)
    time.sleep(0.5)
    safe_click(driver, target_row)

    try:
        body = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.a3s.aiL, div.a3s"))
        )
        driver.execute_script("arguments[0].style.outline='3px solid green'", body)
        text = body.text[:300].replace("\n", " ").strip()
        log(f"Email body scraped: {text[:80]}...")
        return text
    except TimeoutException:
        warn("Could not read email body.")
        return ""


# ─────────────────────────────────────────────
# PHASE 2 — Google Sheets (Selenium)
# ─────────────────────────────────────────────

def phase_sheets(driver, email_text):
    log("--- PHASE 2: Google Sheets ---")

    if GOOGLE_SHEET_URL == "PASTE_YOUR_GOOGLE_SHEET_URL_HERE":
        warn("GOOGLE_SHEET_URL not set — skipping Sheets phase.")
        return

    # Hardcoded fallback if Gmail scraped nothing useful
    content = email_text.strip() if email_text and len(email_text.strip()) > 10 \
        else "New lead identified — follow up required. Source: Gmail inbox triage."

    new_tab(driver, GOOGLE_SHEET_URL)

    # Wait for sheet to load — Name Box is the most reliable indicator
    log("Waiting for spreadsheet to load ...")
    name_box_el = None
    for sel in ["div.waffle-name-box input", ".cell-input", "#t-name-box", "input.waffle-name-box"]:
        try:
            name_box_el = WebDriverWait(driver, 40).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            log(f"Sheet loaded (Name Box found via {sel}).")
            break
        except TimeoutException:
            continue

    if name_box_el is None:
        err("Sheet never loaded — cannot write row.")
        return

    time.sleep(2)

    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Navigate to A1, detect last used row, jump to next empty ──
        name_box_el.click()
        time.sleep(0.2)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        name_box_el.send_keys("A1")
        name_box_el.send_keys(Keys.RETURN)
        time.sleep(0.5)

        # Read A1 value from formula bar to check if sheet is empty
        a1_empty = True
        for fb_sel in ["#t-formula-bar-input", ".cell-input[id*='formula']", "input[id*='formula']"]:
            try:
                fb = driver.find_element(By.CSS_SELECTOR, fb_sel)
                a1_empty = not (fb.get_attribute("value") or "").strip()
                break
            except NoSuchElementException:
                continue

        if a1_empty:
            next_row = "A1"
            log("Sheet is empty — writing to A1.")
        else:
            # Jump to bottom of data in column A, read the row number
            ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.DOWN).key_up(Keys.CONTROL).perform()
            time.sleep(0.4)
            name_box_el.click()
            time.sleep(0.2)
            addr = (name_box_el.get_attribute("value") or "").strip()
            if addr:
                row_num = int("".join(filter(str.isdigit, addr))) + 1
                next_row = f"A{row_num}"
            else:
                next_row = "A2"
            log(f"Writing to {next_row}.")

        # ── Navigate to target cell ──
        name_box_el.click()
        time.sleep(0.2)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        name_box_el.send_keys(next_row)
        name_box_el.send_keys(Keys.RETURN)
        time.sleep(0.4)

        # ── Type the three columns: Timestamp | Type | Content ──
        log("Typing row data ...")
        ActionChains(driver).send_keys(timestamp).perform();          time.sleep(0.15)
        ActionChains(driver).send_keys(Keys.TAB).perform();           time.sleep(0.15)
        ActionChains(driver).send_keys("Gmail Lead").perform();       time.sleep(0.15)
        ActionChains(driver).send_keys(Keys.TAB).perform();           time.sleep(0.15)
        ActionChains(driver).send_keys(content[:200]).perform();      time.sleep(0.15)
        ActionChains(driver).send_keys(Keys.RETURN).perform()
        time.sleep(1)

        # ── Ctrl+S ──
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("s").key_up(Keys.CONTROL).perform()
        time.sleep(2)

        # Scroll back to the row we just wrote so user can see it
        name_box_el.click()
        time.sleep(0.2)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        name_box_el.send_keys(next_row)
        name_box_el.send_keys(Keys.RETURN)
        time.sleep(1)
        log("Row written and saved — visible in sheet.")

    except Exception as e:
        err(f"Sheets write failed: {e}")
        import traceback; traceback.print_exc()


# ─────────────────────────────────────────────
# PHASE 3 — Discord (Selenium)
# ─────────────────────────────────────────────

def phase_discord(driver, email_text):
    log("--- PHASE 3: Discord ---")

    if DISCORD_WEBHOOK_URL == "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
        warn("DISCORD_WEBHOOK_URL not set — skipping Discord phase.")
        return

    # Hardcoded fallback if Gmail scraped nothing useful
    content = email_text.strip() if email_text and len(email_text.strip()) > 10 \
        else "New lead identified — follow up required. Source: Gmail inbox triage."

    message = f"[NEW LEAD] {content[:200]}"

    new_tab(driver, "https://discord.com/app")
    time.sleep(5)  # Discord is slow to boot

    # Wait for the message textbox — the only reliable signal Discord is ready
    log("Waiting for Discord message box ...")
    textbox = None
    for sel in [
        "div[role='textbox'][contenteditable='true']",
        "div[role='textbox']",
        "div[data-slate-editor='true']",
        "div[contenteditable='true'][spellcheck='true']",
    ]:
        try:
            textbox = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            if textbox.is_displayed():
                log(f"Textbox found: {sel}")
                break
            textbox = None
        except TimeoutException:
            textbox = None

    if textbox is None:
        err("Discord message box not found.")
        return

    driver.execute_script("arguments[0].style.outline='3px solid purple'", textbox)
    time.sleep(0.5)

    # ── Type via clipboard (PowerShell) — most reliable for Discord's Slate editor ──
    try:
        safe_msg = message.replace('"', "'")
        ps_cmd = f'Set-Clipboard -Value "{safe_msg}"'
        subprocess.run(["powershell", "-command", ps_cmd], capture_output=True)
        time.sleep(0.3)
        textbox.click()
        time.sleep(0.3)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
        time.sleep(0.8)
        log("Pasted message via clipboard.")
    except Exception as e:
        warn(f"Clipboard paste failed ({e}), falling back to JS insertText ...")
        textbox.click()
        time.sleep(0.3)
        driver.execute_script("""
            arguments[0].focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, arguments[1]);
        """, textbox, message)
        time.sleep(0.8)

    # Confirm text is in the box before sending
    typed = textbox.text.strip()
    if not typed:
        warn("Nothing in textbox — message may not send.")
    else:
        log(f"Text confirmed in box: {typed[:60]}...")

    # ── Send with Enter ──
    # Click the box first to make sure it has focus, THEN press Enter
    textbox.click()
    time.sleep(0.3)
    textbox.send_keys(Keys.RETURN)
    time.sleep(1)
    log("Discord message sent.")
    time.sleep(2)


# ─────────────────────────────────────────────
# PHASE 4 — Google Meet
# ─────────────────────────────────────────────

def phase_meet(driver):
    log("--- PHASE 4: Google Meet ---")
    new_tab(driver, "https://meet.google.com/new")
    time.sleep(5)
    log(f"Meeting room: {driver.current_url}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run():
    log("=== STARTING AUTOMATION ===")

    chrome_exe = find_chrome()
    log(f"Chrome: {chrome_exe}")

    kill_chrome()

    try:
        user_data_dir, profile_dir = clone_profile()
    except Exception as e:
        warn(f"Profile clone failed ({e}) — using fresh profile.")
        user_data_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "chrome_fresh")
        profile_dir   = "Default"
        os.makedirs(user_data_dir, exist_ok=True)

    launch_chrome(user_data_dir, profile_dir, chrome_exe)

    try:
        driver = attach_selenium()

        email_text = phase_gmail(driver)
        time.sleep(3)  # let user see the scraped email

        phase_sheets(driver, email_text)
        time.sleep(5)  # let user see the row written in the sheet

        phase_discord(driver, email_text)
        time.sleep(5)  # let user see the message sent in Discord

        phase_meet(driver)

        log("=== WORKFLOW COMPLETE ===")
        time.sleep(10)

    except WebDriverException as e:
        err(f"WebDriver error: {e}")
    except Exception as e:
        err(f"Unexpected error: {e}")
        import traceback; traceback.print_exc()
    finally:
        log("Done. Browser left open.")


if __name__ == "__main__":
    run()