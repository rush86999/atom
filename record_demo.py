import time
import os
import cv2
import numpy as np
import requests
from selenium import webdriver

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
output_dir = r"C:\Users\Mannan Bajaj\.gemini\antigravity\brain\a4cfcbdf-5faa-4879-9494-18629dcea59e"

try:
    print("Launching Chrome in background...")
    options = webdriver.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--headless=new')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(300)
    driver.set_window_size(1920, 1080)
    
    routes = [
        {"name": "automations_demo", "url": "/automations"},
        {"name": "finance_demo", "url": "/finance"},
        {"name": "sales_demo", "url": "/sales"},
        {"name": "marketing_demo", "url": "/marketing"},
        {"name": "analytics_demo", "url": "/analytics"},
        {"name": "dev_studio_demo", "url": "/dev-studio"},
        {"name": "agents_demo", "url": "/agents"},
        {"name": "marketplace_demo", "url": "/marketplace"},
        {"name": "health_demo", "url": "/health"}
    ]

    for route in routes:
        url = f"http://localhost:3000{route['url']}"
        print(f"\nPre-warming {url} to trigger Next.js cache...")
        try:
            # We hit the endpoint with requests first so Webpack handles the long SSR compilation.
            # This prevents the Selenium socket from timing out while waiting for Node.js
            requests.get(url, timeout=300)
        except Exception as e:
            print(f"Pre-warm compilation hit a timeout, proceeding anyway: {e}")

        print(f"Recording {route['name']}...")
        driver.get(url)
        time.sleep(5) # Wait for client-side React hydration
        
        filename = os.path.join(output_dir, f"{route['name']}.mp4")
        
        img_data = driver.get_screenshot_as_png()
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        height, width, layers = frame.shape
        out = cv2.VideoWriter(filename, fourcc, 10.0, (width, height))
        
        for _ in range(10):
            img_data = driver.get_screenshot_as_png()
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            out.write(frame)
            
        for step in range(30):
            driver.execute_script("window.scrollBy(0, 40);")
            img_data = driver.get_screenshot_as_png()
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            out.write(frame)
            
        for _ in range(10):
            img_data = driver.get_screenshot_as_png()
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            out.write(frame)
            
        for step in range(30):
            driver.execute_script("window.scrollBy(0, -40);")
            img_data = driver.get_screenshot_as_png()
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            out.write(frame)
            
        out.release()
        print(f"Saved {filename}")

    print("All demos complete. Closing browser...")
    driver.quit()
except Exception as e:
    print(f"Error occurred: {e}")
    try:
        driver.quit()
    except:
        pass
