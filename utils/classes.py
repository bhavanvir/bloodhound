from typing import List, Optional
from pydantic import BaseModel


class Stock(BaseModel):
    name: str
    type: str
    amount: str
    date: Optional[str]
    transaction_date: Optional[str]
    options: Optional[str]


class Individual(BaseModel):
    first_name: str
    last_name: str
    position: str
    links: List[str] = []


class Portfolio(Individual):
    stocks: List[Stock] = []
