
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

def test_selenium():
    print("Starting Selenium test...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.google.com")
        print(f"Page title: {driver.title}")
        driver.quit()
        print("Selenium test successful!")
    except Exception as e:
        print(f"Selenium test failed: {e}")

if __name__ == "__main__":
    test_selenium()
