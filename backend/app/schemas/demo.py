"""Response models for the simulated demo endpoints."""

from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str


class UsersResponse(BaseModel):
    users: list[User]


class Product(BaseModel):
    id: int
    name: str
    price: float


class ProductsResponse(BaseModel):
    products: list[Product]


class Order(BaseModel):
    id: int
    user_id: int
    total: float
    status: str


class OrdersResponse(BaseModel):
    orders: list[Order]


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[Product]


class ReportRow(BaseModel):
    label: str
    value: float


class ReportResponse(BaseModel):
    title: str
    period: str
    rows: list[ReportRow]
