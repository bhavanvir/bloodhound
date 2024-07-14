import os
import requests
from dotenv import load_dotenv
import time
import json
import re
from typing import List
from pydantic import BaseModel
from bs4 import BeautifulSoup
from tqdm import tqdm

load_dotenv()

CSRF_TOKEN = os.getenv("CSRF_TOKEN", "")
SESSION_ID = os.getenv("SESSION_ID", "")


# Define the data models
class Stock(BaseModel):
    name: str
    type: str  # 'buy' or 'sell'
    amount: str
    date: str
    transaction_date: str = None
    options: str = None


class Politician(BaseModel):
    firstName: str
    lastName: str
    position: str
    stocks: List[Stock]


class Individual(BaseModel):
    first_name: str
    last_name: str
    position: str
    links: List[str] = []


def parse_json_and_filter() -> List[Individual]:
    # TODO: Should fetch the file with the largest timestamp
    with open("data/individuals_1720915487.json", "r") as f:
        json_data = json.load(f)
    individuals = [Individual(**item) for item in json_data]
    for individual in individuals:
        individual.links = removeDocuments(individual.links)
    return individuals


def removeDocuments(strings: List[str]) -> List[str]:
    return [s for s in strings if "/paper/" not in s]


def aggregate_data(individual: Individual) -> Politician:
    stocks = []
    for link in individual.links:
        stock = fetch_data(link)
        if stock:
            stocks.append(stock)
    politician = Politician(
        firstName=individual.first_name,
        lastName=individual.last_name,
        position=individual.position,
        stocks=stocks,
    )
    return politician


def fetch_data(link: str) -> List[Stock] | None:
    cookies = {"csrftoken": CSRF_TOKEN, "sessionid": SESSION_ID}
    response = requests.get(url=f"https://efdsearch.senate.gov{link}", cookies=cookies)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        date = get_date(soup)
        if "annual" in link:
            return get_annual_stocks(soup, date)
        elif "ptr" in link:
            return get_ptr_stocks(soup, date)
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")


def get_annual_stocks(soup: BeautifulSoup, date: str) -> List[Stock] | None:
    h3_assets = soup.find(string="Part 3. Assets")
    assets_table = None
    stocks = []
    if h3_assets:
        parent = h3_assets.find_parent().find_parent().find_parent()
        if parent:
            assets_table = parent.find("table")

        if assets_table:
            rows = assets_table.find_all("tr", class_="nowrap")
            for row in rows:
                columns = row.find_all("td")
                if len(columns) > 2:
                    asset_name = columns[1].get_text(strip=True)
                    asset_type = columns[2].get_text(strip=True)
                    if (
                        "Mutual Funds" in asset_type
                        or "Corporate Securities" in asset_type
                    ):
                        value = columns[4].get_text(strip=True)
                        type = "sell" if "None" in value else "buy"
                        stock = Stock(
                            name=asset_name,
                            type=type,
                            amount=value,
                            date=date if date else None,
                        )
                        stocks.append(stock)
        else:
            return None
    return stocks


def get_ptr_stocks(soup, date) -> List[Stock] | None:
    stocks = []
    assets_table = soup.find("table")
    if assets_table:
        # Iterate through each row (tr) in the table
        for row in assets_table.find_all("tr"):
            # Get all column cells (td) in this row
            columns = row.find_all("td")
            if columns:  # Ensure we have columns
                # Extract and print each column value
                column_val = [column.get_text(strip=True) for column in columns]
                transaction_date = column_val[1]
                asset_name = column_val[4]
                asset_type = column_val[5]
                transaction_type = column_val[5]
                value = column_val[7]
                if "Stock" in asset_type:
                    stock = stock = Stock(
                        name=asset_name,
                        amount=value,
                        date=date if date else None,
                        transaction_date=transaction_date,
                        type=transaction_type,
                    )
                    if "Option" in asset_type:
                        option_index = asset_name.find("Option")
                        option_part = asset_name[option_index:]
                        remaining_part = asset_name[:option_index].strip()
                        stock.name = remaining_part
                        stock.options = option_part
                    stocks.append(stock)
    else:
        print("No assets table found")
    return stocks


def get_date(soup: BeautifulSoup) -> str | None:
    pattern = re.compile(r"Filed\s+\d{2}/\d{2}/\d{4}\s+@\s+\d{1,2}:\d{2}\s+[APM]{2}")
    date_element = soup.find(string=pattern)
    if date_element:
        date_text = date_element.get_text()
        patterns = [r"\b\d{2}/\d{2}/\d{4}\b"]

        def find_matches(text, patterns):
            matches = []
            for pattern in patterns:
                matches.extend(re.findall(pattern, text))
            return matches

        matches = find_matches(date_text, patterns)
        return matches[0] if matches else None
    else:
        print("No date element element containing 'Filed' found")


individuals = parse_json_and_filter()
politicians = []
for individual in tqdm(individuals):
    politicians.append(fetch_data(individual))

current_timestamp = int(time.time())
with open(f"data/politicians_{current_timestamp}.json", "w") as f:
    json.dump([politician.model_dump() for politician in politicians], f, indent=2)
