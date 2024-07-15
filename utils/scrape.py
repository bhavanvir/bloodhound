import os
import json

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from tqdm import tqdm

from helpers import COOKIES, HEADERS

load_dotenv()

URL_PREFIX = "https://efdsearch.senate.gov"


class Stock(BaseModel):
    name: str
    type: str
    amount: str
    date: str
    transaction_date: Optional[str]
    options: Optional[str]


class Individual(BaseModel):
    first_name: str
    last_name: str
    position: str
    links: List[str] = []


class Portfolio(Individual):
    stocks: List[Stock] = []


def fetch_latest_file(file_prefix: str) -> str:
    root_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(root_dir, "data")

    file_map = {}
    for file in os.listdir(data_dir):
        if file.startswith(file_prefix):
            timestamp = os.path.splitext(file)[0].split("_")[-1]
            file_map[file] = int(timestamp)

    latest_file = max(file_map, key=lambda x: file_map[x])
    return os.path.join(data_dir, latest_file)


def filter_data(data: List[Individual], exclude: List[str]) -> List[Individual]:
    for entry in data:
        for link in entry.links:
            if any([keyword in link for keyword in exclude]):
                entry.links.remove(link)
    return data


def fetch_data(link: str) -> None:
    def parse_ptr(soup: BeautifulSoup) -> None:
        print(soup.prettify())

    def parse_annual(soup: BeautifulSoup) -> None:
        pass

    response = requests.get(url=URL_PREFIX + link, cookies=COOKIES, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    print(f"Fetching data from: {URL_PREFIX + link}")

    if "ptr" in link:
        parse_ptr(soup)
    elif "annual" in link:
        parse_annual(soup)


latest_file = fetch_latest_file(file_prefix="individuals")

data = [Individual(**entry) for entry in json.load(open(latest_file))]
data = filter_data(data, exclude=["paper"])
