import os
from dotenv import load_dotenv

load_dotenv()

CSRF_TOKEN = os.getenv("CSRF_TOKEN", "")
SESSION_ID = os.getenv("SESSION_ID", "")

COOKIES = {
    "csrftoken": CSRF_TOKEN,
    "sessionid": SESSION_ID,
}

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-CSRFToken": CSRF_TOKEN,
    "Origin": "https://efdsearch.senate.gov",
    "Connection": "keep-alive",
    "Referer": "https://efdsearch.senate.gov/search/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
