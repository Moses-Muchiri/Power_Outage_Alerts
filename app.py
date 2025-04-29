from dotenv import load_dotenv
import os
from PIL import Image
from io import BytesIO
from telegram import Bot
import pytesseract
import asyncio
import colorama
from colorama import Fore
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
import time
from datetime import datetime, timezone
import re
import aiofiles
import json

colorama.init(autoreset=True)

def print_status(message, success=True):
    print(Fore.GREEN + message if success else Fore.RED + message)

print_status("Loading environment variables...")

load_dotenv('.env')

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")

edge_options = Options()
edge_options.add_argument('--headless')
edge_options.add_argument('--disable-extensions')
edge_options.add_argument('--disable-gpu')
edge_options.add_argument('--no-sandbox')
edge_options.add_argument('--disable-dev-shm-usage')
edge_service = Service(executable_path=os.getenv("EDGE_DRIVER_PATH"))
driver = webdriver.Edge(service=edge_service, options=edge_options)

def convert_image_to_rgb(img):
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return img

async def send_telegram_message(message, image_path=None, retries=3):
    try:
        await bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text=message)
        if image_path:
            with open(image_path, 'rb') as image_file:
                await bot.send_document(chat_id=os.getenv("TELEGRAM_CHAT_ID"), document=image_file)
        print_status("Message sent successfully!")
    except Exception as e:
        if retries > 0:
            print_status(f"Failed to send message: {e}. Retrying...", success=False)
            time.sleep(5)
            await send_telegram_message(message, image_path, retries-1)
        else:
            print_status(f"Failed to send message after retries: {e}", success=False)

def download_image(url):
    print_status(f"Downloading image from {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        print_status("Image downloaded successfully!")
        return img
    except requests.RequestException as e:
        print_status(f"Failed to download image: {e} (Status Code: {response.status_code if 'response' in locals() else 'Unknown'})", success=False)
        return None

def search_for_keywords(text):
    keywords = ['membley', 'membly', 'kiwanja', 'githunguri ranching', 'jacridge']
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)

async def login_to_twitter():
    print_status("Navigating to Twitter login page...")
    driver.get('https://twitter.com')
    twitter_cookie = json.loads(os.getenv("TWITTER_COOKIE"))
    driver.add_cookie(twitter_cookie)
    driver.refresh()
    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, '//nav')))
        print_status("Login successful!")
        return True
    except Exception as e:
        print_status(f"Login failed: {e}", success=False)
        driver.save_screenshot('login_error.png')
        return False

async def scan_kplc_for_outages():
    if not await login_to_twitter():
        print_status("Exiting script due to login failure.", success=False)
        return
    print_status("Navigating to KPLC Twitter page...")
    driver.get('https://twitter.com/KenyaPower_Care')
    try:
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, '//article[@role="article"]')))
        print_status("Tweets found on the page!")
    except TimeoutException:
        driver.save_screenshot('timeout_error.png')
        print_status("Failed to find tweets within the specified time frame. Check timeout_error.png for details.", success=False)
        return

    tweets = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        tweet_elements = driver.find_elements(By.XPATH, '//article[@role="article"]')
        for tweet_element in tweet_elements:
            try:
                tweet_text = tweet_element.find_element(By.XPATH, './/div[2]/div[2]/div[2]').text
                tweet_date = tweet_element.find_element(By.XPATH, './/time').get_attribute('datetime')
                tweet_datetime = datetime.strptime(tweet_date, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
                if tweet_datetime.date() == datetime.now(timezone.utc).date():
                    images = tweet_element.find_elements(By.XPATH, './/img[@alt="Image"]')
                    media_urls = [img.get_attribute('src') for img in images]
                    tweets.append({"text": tweet_text, "date": tweet_date, "media_urls": media_urls})
            except Exception as e:
                print_status(f"Error extracting tweet: {e}", success=False)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    found_outage = False
    temp_image_paths = []
    image_counter = 1

    for tweet in tweets:
        for media_url in tweet['media_urls']:
            img = download_image(media_url)
            if img:
                img = convert_image_to_rgb(img)
                temp_image_path = f"temp_image{image_counter}.jpg"
                img.save(temp_image_path, format='JPEG')
                image_counter += 1
                print_status(f"Scanning image {temp_image_path} with Tesseract...")
                extracted_text = pytesseract.image_to_string(img)
                if search_for_keywords(extracted_text):
                    found_outage = True
                    temp_image_paths.append(temp_image_path)

    if found_outage:
        await send_telegram_message(f"Found preplanned blackout for your area from the scan on {datetime.now().date()}.", temp_image_paths[0])
    else:
        placeholder_image_path = "no_blackout.jpg"
        if not os.path.exists(placeholder_image_path):
            img = Image.new('RGB', (400, 200), color='white')
            img.save(placeholder_image_path)
        await send_telegram_message("No preplanned blackout found for your area tomorrow.", placeholder_image_path)

    async with aiofiles.open('tweets_extracted.txt', 'w') as file:
        await file.write('\n'.join([tweet['text'] for tweet in tweets]))

if __name__ == "__main__":
    asyncio.run(scan_kplc_for_outages())
    driver.quit()
