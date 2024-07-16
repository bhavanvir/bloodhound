import os
import json
import re
import time

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv
from typing import List, Optional

from helpers import COOKIES, HEADERS
from classes import Individual, Portfolio, Stock

load_dotenv()

URL_PREFIX = "https://efdsearch.senate.gov"


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


def aggregate_data(data: List[Individual]) -> List[Portfolio]:
    portfolios = []
    for entry in data:
        stocks = []
        poltician_name = f"{entry.first_name} {entry.last_name}"
        print(f"Aggregating data for: {poltician_name}")
        for link in entry.links:
            stock = fetch_data(link)
            if stock is None:
                continue
            stocks.extend(stock)

        portfolio = Portfolio(
            politician_name=poltician_name,
            position=entry.position,
            stocks=stocks,
        )
        portfolios.append(portfolio)
    return portfolios


def fetch_data(link: str) -> Optional[List[Stock]]:
    def parse_ptr(soup: BeautifulSoup) -> List[Stock]:
        assets_table = soup.find("table")
        if assets_table is None:
            print("Failed to fetch assets table for Period Report")
            return []
        return get_ptr_assets(assets_table, get_date(soup))

    def parse_annual(soup: BeautifulSoup) -> List[Stock]:
        asset_title = soup.find(string="Part 3. Assets")
        asset_parent = asset_title.find_parent("section") if asset_title else None
        assets_table = asset_parent.find("table") if asset_parent else None
        if assets_table is None:
            print("Failed to fetch assets table for Annual Report")
            return []
        return get_annual_assets(assets_table, get_date(soup))

    response = requests.get(url=URL_PREFIX + link, cookies=COOKIES, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    if response.status_code != 200:
        print(f"Failed to fetch data from: {URL_PREFIX + link}")
        return

    print(f"Fetching data from: {URL_PREFIX + link}")

    if "ptr" in link:
        return parse_ptr(soup)
    elif "annual" in link:
        return parse_annual(soup)


def get_ptr_assets(
    assets_table: Tag | NavigableString, date: str | None
) -> List[Stock]:
    stocks = []
    for row in assets_table.find_all("tr"):  # type: ignore
        columns = [column.get_text(strip=True) for column in row.find_all("td")]
        if not columns:
            continue
        asset_name = columns[4]
        asset_type = columns[5]
        transaction_type, transaction_date = columns[6], columns[1]
        amount = columns[7]
        stock = None
        if "Stock" in asset_type:
            stock = Stock(
                name=asset_name,
                amount=amount,
                date=date if date else None,
                transaction_date=transaction_date,
                type=transaction_type,
                options=None,
            )
            if "Option" in asset_type:
                option_index = asset_name.find("Option")
                option_part = asset_name[option_index:]
                stock_name = asset_name[:option_index].strip()
                stock.name = stock_name
                stock.options = option_part
        stocks.append(stock) if stock else None
    return stocks


def get_annual_assets(
    assets_table: Tag | NavigableString, date: str | None
) -> List[Stock]:
    stocks = []
    rows = assets_table.find_all("tr", class_="nowrap")  # type: ignore
    for row in rows:
        columns = [column.get_text(strip=True) for column in row.find_all("td")]
        if not columns:
            continue
        asset_name = columns[1]
        asset_type = columns[2]
        if "Mutual Funds" in asset_type or "Corporate Securities" in asset_type:
            value = columns[4]
            type = "sell" if "None" in value else "buy"
            stock = Stock(
                name=asset_name,
                type=type,
                amount=value,
                date=date if date else None,
                transaction_date=None,
                options=None,
            )
            stocks.append(stock) if stock else None
    return stocks


def get_date(soup: BeautifulSoup) -> str | None:
    pattern = re.compile(r"Filed.+[APM]{2}")
    date_element = soup.find(string=pattern)
    if date_element:
        date_text = date_element.get_text()
        match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", date_text)
        return match.group() if match else None
    else:
        print("No date element element containing 'Filed' found")


latest_file = fetch_latest_file(file_prefix="individuals")

data = [Individual(**entry) for entry in json.load(open(latest_file))]
data = filter_data(data, exclude=["paper"])
portfolios = aggregate_data(data)

current_timestamp = int(time.time())
with open(f"data/portfolio_{current_timestamp}.json", "w") as f:
    json.dump([portfolio.model_dump() for portfolio in portfolios], f, indent=2)
