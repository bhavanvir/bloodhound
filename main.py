import re
from typing import List, Optional, Tuple

from pydantic import BaseModel
from playwright.sync_api import (
    Browser,
    sync_playwright,
    Playwright,
    Page,
    BrowserContext,
)
from bs4 import BeautifulSoup
from rich import print

BASE_URL = "https://efdsearch.senate.gov/search/home/"
BASE_TIMEOUT = 1000

RE_POSITION = re.compile(r"(Senator|Candidate)", re.IGNORECASE)


class Stock(BaseModel):
    transaction_date: str
    owner: str
    ticker: str
    asset_name: str
    asset_type: str
    transaction_type: str
    amount: Tuple[int, int]
    comment: Optional[str]

    @staticmethod
    def extract_amount(html: str) -> Tuple[int, int]:
        # match = re.search(r"\$(\d+),(\d+)", html)
        # return int(match.group(1)), int(match.group(2)) if match else (0, 0)
        pass


class Individual(BaseModel):
    first_name: str
    last_name: str
    position: str
    stocks: List[Stock] = []

    @staticmethod
    def extract_position(html: str) -> str:
        match = RE_POSITION.search(html)
        return match.group(1) if match else "N/A"


def check_agreement(page: Page) -> None:
    get_access = page.locator('h4:has-text("Get Access")')

    if get_access.is_visible():
        page.locator('input#agree_statement[type="checkbox"]').click()
        print("[green]Agreement checked[/green]")


def check_report_types(page: Page, report_types: List[str]) -> None:
    for report_type in report_types:
        page.locator(f'label:text-is("{report_type}")').click()
        print(f"[green]Checked {report_type}[/green]")


def check_filer_types(page: Page, filer_types: List[str]) -> None:
    for filer_type in filer_types:
        page.locator(f'label:text-is("{filer_type}")').click()
        print(f"[green]Checked {filer_type}[/green]")


def parse_transactions(page: Page, individual: Individual) -> None:
    soup = BeautifulSoup(page.content(), "html.parser")


def parse_search_results(page: Page, context: BrowserContext) -> None:
    soup = BeautifulSoup(page.content(), "html.parser")
    table = soup.find("table")

    if not table:
        print("[red]Table not found![/red]")
        return

    for row in table.find_all("tr"):  # type: ignore
        columns = [column.text.strip() for column in row.find_all("td")]
        if not columns:
            continue

        first_name, last_name, position, report_type = columns[:4]

        individual = Individual(
            first_name=first_name,
            last_name=last_name,
            position=Individual.extract_position(position),
        )

        link = page.locator(f'a:text-is("{report_type}")')
        url = link.get_attribute("href")
        if "paper" in url:  # type: ignore
            print(f"[red]Skipping {individual.first_name} {individual.last_name}[/red]")
            continue

        with context.expect_page() as new_page_info:
            link.click()

        new_page = new_page_info.value
        new_page.wait_for_load_state()

        parse_transactions(new_page, individual)
        break


def run(p: Playwright) -> None:
    chrome = p.chromium
    browser = chrome.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)

    check_agreement(page)
    check_report_types(page, report_types=["Periodic Transactions"])
    check_filer_types(page, filer_types=["Senator", "Candidate", "Former Senator"])

    page.locator('button:text-is("Search Reports")').click()

    page.wait_for_timeout(BASE_TIMEOUT)

    parse_search_results(page, context)

    browser.close()


with sync_playwright() as p:
    run(p)
