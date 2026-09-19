"""Response models for the simulated demo endpoints."""

from pydantic import BaseModel, ConfigDict, Field


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


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are rejected, catching typos

    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=99)


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(ge=1)
    items: list[OrderItem] = Field(min_length=1, max_length=20)


class CreatedOrder(BaseModel):
    id: str
    user_id: int
    status: str
    total: float
    items: list[OrderItem]
