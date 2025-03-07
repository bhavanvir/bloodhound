import time
import json
import re
from typing import List, Optional, Tuple, Dict

from pydantic import BaseModel
from playwright.sync_api import (
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
RE_AMOUNT = re.compile(r"[\$,]")
RE_COMPANIES = re.compile(r"\s*\n\s*\n\s*")
RE_ENTRIES = re.compile(r"\d+(?:,\d+)*")


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
        v1, v2 = map(int, RE_AMOUNT.sub("", html).split(" - "))
        return (v1, v2)


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
    table = soup.find("table")

    if not table:
        print("\t[red]Table not found![/red]")
        return

    for row in table.find_all("tr"):  # type: ignore
        columns = [column.text.strip() for column in row.find_all("td")]
        if not columns:
            continue

        (
            transaction_date,
            owner,
            ticker,
            asset_name,
            asset_type,
            transaction_type,
            amount,
            comment,
        ) = columns[1:]

        if ticker == "--":
            print("\t[yellow]Skipping row without ticker[/yellow]")
            continue

        if comment == "--":
            comment = None

        # Case where there are multiple stocks
        tickers = ticker.strip().split()
        asset_names = RE_COMPANIES.split(asset_name)
        asset_names = [asset_name.replace("\n", " ") for asset_name in asset_names]

        comments = {t: None for t in tickers}

        if comment:
            matched_tickers = [t for t in tickers if t in comment]

            if matched_tickers:
                for ticker in matched_tickers:
                    comments[ticker] = comment
            else:
                for ticker in tickers:
                    comments[ticker] = comment

        for ticker, asset_name in zip(tickers, asset_names):
            individual.stocks.append(
                Stock(
                    transaction_date=transaction_date,
                    owner=owner,
                    ticker=ticker,
                    asset_name=asset_name,
                    asset_type=asset_type,
                    transaction_type=transaction_type,
                    amount=Stock.extract_amount(amount),
                    comment=comments[ticker],
                )
            )


def parse_search_results(
    page: Page, context: BrowserContext, individuals: Dict[Tuple[str, str], Individual]
) -> None:
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

        name_key = (first_name, last_name)
        if name_key not in individuals:
            individuals[name_key] = Individual(
                first_name=first_name,
                last_name=last_name,
                position=Individual.extract_position(position),
            )
            print(f"[green]Added {first_name} {last_name}[/green]")
        else:
            print(f"[yellow]Updating stocks for {first_name} {last_name}[/yellow]")

        individual = individuals[name_key]

        row_link = row.find("a")
        row_url = row_link["href"]
        if "paper" in row_url:  # type: ignore
            print("\t[yellow]Skipping due to paper type link[/yellow]")
            continue

        with context.expect_page() as new_page_info:
            page.locator(f'a[href="{row_url}"]').click()

        new_page = new_page_info.value
        new_page.wait_for_load_state()

        parse_transactions(new_page, individual)

        new_page.close()

    page.locator('a#filedReports_next[aria-controls="filedReports"]').click()

    page.wait_for_timeout(BASE_TIMEOUT)


def run(p: Playwright) -> None:
    chrome = p.chromium
    browser = chrome.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)

    check_agreement(page)
    check_report_types(page, report_types=["Periodic Transactions"])
    check_filer_types(page, filer_types=["Senator", "Candidate", "Former Senator"])

    page.locator('button:text-is("Search Reports")').click()

    page.wait_for_timeout(BASE_TIMEOUT)

    report_info = page.locator('div#filedReports_info[role="status"]').inner_text()
    start, step, stop = map(
        lambda x: int(x.replace(",", "")), RE_ENTRIES.findall(report_info)
    )

    individuals = {}
    for _ in range(start, stop, step):
        parse_search_results(page, context, individuals)

    all_individuals = list(individuals.values())

    print(
        f"[green]Successfully scraped {len(all_individuals)} individuals! Saving output to the data directory...[/green]"
    )

    current_timestamp = int(time.time())
    with open(f"data/individuals_{current_timestamp}.json", "w") as file:
        file.write(
            json.dumps(
                [individual.model_dump() for individual in all_individuals], indent=2
            )
        )

    browser.close()


with sync_playwright() as p:
    run(p)
