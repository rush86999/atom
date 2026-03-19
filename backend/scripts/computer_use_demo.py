
import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run_demo():
    print("[START] Starting ATOM Computer Use Demo...")
    
    # Configuration
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    demo_apps_dir = os.path.join(base_dir, "demo_apps")
    
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Comment out to see the magic!
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. GMAIL - Lead Detection
        gmail_path = "file://" + os.path.join(demo_apps_dir, "gmail.html").replace("\\", "/")
        print(f"[GMAIL] Navigating to Gmail: {gmail_path}")
        driver.get(gmail_path)
        time.sleep(2)
        
        # Simulate "Extracting" data
        print("[AI] AI Agent: Identifying lead email...")
        lead_row = driver.find_element(By.ID, "leadEmailRow")
        driver.execute_script("arguments[0].style.border = '3px solid #4285f4';", lead_row)
        time.sleep(1.5)
        
        print("[GMAIL] Opening lead email...")
        lead_row.click()
        time.sleep(2)
        
        # 2. ZOHO CRM - Lead Creation
        zoho_path = "file://" + os.path.join(demo_apps_dir, "zoho.html").replace("\\", "/")
        print(f"[ZOHO] Navigating to Zoho CRM: {zoho_path}")
        driver.get(zoho_path)
        time.sleep(2)
        
        print("[ZOHO] Creating lead in Zoho...")
        driver.find_element(By.ID, "btnNewLead").click()
        time.sleep(1)
        
        driver.find_element(By.ID, "firstName").send_keys("Sarah")
        time.sleep(0.5)
        driver.find_element(By.ID, "lastName").send_keys("Jenkins")
        time.sleep(0.5)
        driver.find_element(By.ID, "company").send_keys("Project X")
        time.sleep(0.5)
        driver.find_element(By.ID, "email").send_keys("sarah.j@projectx.com")
        time.sleep(1)
        
        print("[ZOHO] Saving lead...")
        driver.find_element(By.ID, "submitLeadBtn").click()
        time.sleep(2)
        
        # 3. SLACK - Notification & HITL
        slack_path = "file://" + os.path.join(demo_apps_dir, "slack.html").replace("\\", "/")
        print(f"[SLACK] Navigating to Slack: {slack_path}")
        driver.get(slack_path)
        time.sleep(1.5)
        
        print("[SLACK] Sending notification to Slack...")
        driver.execute_script("window.triggerAlert()")
        time.sleep(2)
        
        print("[SLACK] Waiting for Human-In-The-Loop (HITL) approval...")
        # In a real demo, we wait for the user to click the button in the browser
        # We can poll for the 'approvedMsg' display state
        approved = False
        timeout = 60 # 60 seconds max wait
        start_time = time.time()
        
        while not approved and (time.time() - start_time) < timeout:
            msg = driver.find_element(By.ID, "approvedMsg")
            if msg.is_displayed():
                approved = True
                print("[SLACK] HITL Approved!")
            time.sleep(1)
            
        if not approved:
            print("[WARNING] HITL Timeout. Proceeding anyway for demo...")

        time.sleep(1)
        
        # 4. ZOOM - Meeting Completion
        zoom_path = "file://" + os.path.join(demo_apps_dir, "zoom.html").replace("\\", "/")
        print(f"[ZOOM] Navigating to Zoom: {zoom_path}")
        driver.get(zoom_path)
        time.sleep(4) # Let the user see the confirmation
        
        print("[SUCCESS] Workflow Complete!")
        
    except Exception as e:
        print(f"[ERROR] Demo execution failed: {e}")
    finally:
        print("[FINISH] Closing browser in 3 seconds...")
        time.sleep(3)
        driver.quit()

if __name__ == "__main__":
    run_demo()
