# test_browser.py

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()

options.binary_location = "/usr/bin/chromium"

options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

driver.get("https://fbref.com")

print(driver.title)

driver.quit()