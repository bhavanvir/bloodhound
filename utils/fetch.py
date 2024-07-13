import time
import os
import json
import re
import requests
from tqdm import tqdm
from typing import Dict, Any, List
from pydantic import BaseModel

TOTAL_PER_PAGE = "100"

RE_LINK = re.compile(r'href="([^"]+)"')
RE_POSITION = re.compile(r"(Senator|Candidate)", re.IGNORECASE)


class Individual(BaseModel):
    first_name: str
    last_name: str
    position: str
    links: List[str] = []

    @staticmethod
    def extract_href(html: str) -> str:
        match = RE_LINK.search(html)
        return match.group(1) if match else ""

    @staticmethod
    def extract_position(html: str) -> str:
        match = RE_POSITION.search(html)
        return match.group(1) if match else "N/A"


def fetch_data(page: str = "1") -> Dict[str, Any]:
    cookies = {
        "csrftoken": "1eXgZmJ56JiAHME5gsU113SU7EJmxLZFX15ssGGqtI9NfecUsqlrdujx9KO5jDR7",
        "sessionid": "gAWVGAAAAAAAAAB9lIwQc2VhcmNoX2FncmVlbWVudJSIcy4:1sSWU7:Yr6Xrsj60XfdwBp-J_I7-Q6Eb24",
    }

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-CSRFToken": "1eXgZmJ56JiAHME5gsU113SU7EJmxLZFX15ssGGqtI9NfecUsqlrdujx9KO5jDR7",
        "Origin": "https://efdsearch.senate.gov",
        "Connection": "keep-alive",
        "Referer": "https://efdsearch.senate.gov/search/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    data = {
        "draw": page,
        "columns[0][data]": "0",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "true",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "1",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "2",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "true",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "3",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "4",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        "order[0][column]": "1",
        "order[0][dir]": "asc",
        "order[1][column]": "0",
        "order[1][dir]": "asc",
        "start": "0",
        "length": TOTAL_PER_PAGE,
        "search[value]": "",
        "search[regex]": "false",
        "report_types": "[7, 11]",
        "filer_types": "[1, 4, 5]",
        "submitted_start_date": "01/01/2012 00:00:00",
        "submitted_end_date": "",
        "candidate_state": "",
        "senator_state": "",
        "office_id": "",
        "first_name": "",
        "last_name": "",
    }

    response = requests.post(
        "https://efdsearch.senate.gov/search/report/data/",
        cookies=cookies,
        headers=headers,
        data=data,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data. Status code: {response.status_code}")

    json_data = json.loads(response.text)
    if json_data["result"] != "ok":
        raise Exception(f"Failed to fetch data. Result: {json_data['result']}")

    return json_data


def create_individuals(data: List[List[str]]) -> List[Individual]:
    individuals_dict = {}
    for entry in data:
        first_name, last_name, full_title, link_html, _ = entry

        first_name = first_name.strip().title()
        last_name = last_name.strip().title()

        full_name = f"{first_name} {last_name}"
        href = Individual.extract_href(link_html)
        position = Individual.extract_position(full_title)

        if full_name in individuals_dict:
            individuals_dict[full_name].links.append(href)
        else:
            individuals_dict[full_name] = Individual(
                first_name=first_name,
                last_name=last_name,
                links=[href],
                position=position,
            )

    return list(individuals_dict.values())


initial_response = fetch_data()

total_records = initial_response["recordsTotal"]
total_pages = -(total_records // -int(TOTAL_PER_PAGE))  # Ceiling division

all_individuals = []

for page in tqdm(range(1, total_pages + 1)):
    response = fetch_data(page=str(page))
    individuals = create_individuals(response["data"])
    all_individuals.extend(individuals)

current_timestamp = int(time.time())
with open(f"data/individuals_{current_timestamp}.json", "w") as file:
    file.write(
        json.dumps([individual.dict() for individual in all_individuals], indent=2)
    )
