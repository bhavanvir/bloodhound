import json
import re
from typing import List
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

cookies = {
    "33a5c6d97f299a223cb6fc3925909ef7":"2c6ec76a3a0e0fd65cbffea92fc962e9",
    "csrftoken":"u2BgzcQkc0OCiCfGy6nPQwnIbulPrSXnZ8AGE22Js9W684CpCl3h5Q8ivwbnB9z1",
    "sessionid":"gAWVGAAAAAAAAAB9lIwQc2VhcmNoX2FncmVlbWVudJSIcy4:1sSptI:-Q4TO7u5blfprQMqYLEFY3m26FA",
}

# Define the data models
class Stock(BaseModel):
    name: str
    type: str  # 'buy' or 'sell'
    amount: str
    date: str = None

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

def main():
    individuals=parse_json_and_filter()
    politicians = []
    for individual in individuals:
        politicians.append(fetch_data(individual))
    print(politicians)
    write_to_json(politicians)    

def parse_json_and_filter():
    with open('data/individuals_1720915487.json', 'r') as f:
        json_data = json.load(f)
    individuals = [Individual(**item) for item in json_data]
    for individual in individuals:
        individual.links = removeDocuments(individual.links)
    return individuals    

def removeDocuments(strings):
    return [s for s in strings if '/paper/' not in s]

def fetch_data(individual):
    stocks=[]
    for link in individual.links:
        response = requests.get(url=f"https://efdsearch.senate.gov{link}",cookies=cookies)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Find the table containing assets
            h3_assets = soup.find(string="Part 3. Assets")
            print(h3_assets)
            assets_table = None
            if h3_assets:
                # Find the parent of the <h3> element
                parent = h3_assets.find_parent().find_parent().find_parent()
                print(parent)
                if parent:
                    # Find the <table> within this parent
                    assets_table = parent.find('table')
                    print(assets_table) 

            if assets_table:
                rows = assets_table.find_all('tr', class_='nowrap')
                
                # Iterate through each row and extract data
                for row in rows:
                    columns = row.find_all('td')
                    if len(columns) > 2:
                        asset_name = columns[1].get_text(strip=True)
                        asset_type = columns[2].get_text(strip=True)
                        if "Mutual Funds" in asset_type or "Corporate Securities" in asset_type:
                            value = columns[4].get_text(strip=True)
                            income = columns[6].get_text(strip=True)
                            type = "sell" if "None" in value else "buy"
                            stock=Stock(name=asset_name, type=type, amount= value)
                            stocks.append(stock)
            else:
                print("Assets table not found.")
        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
    politician=Politician(firstName=individual.first_name, lastName=individual.last_name, position=individual.position, stocks=stocks)
    return politician

def write_to_json(politicians):
    with open('data/politicians.json', 'w') as f:
        json.dump([politician.dict() for politician in politicians], f, indent=2)

main()