"""Fixed fake data for the demo endpoints. It never touches the database."""

from collections.abc import Sequence

from app.schemas.demo import Order, OrderItem, Product, ReportResponse, ReportRow, User

DEMO_USERS = (
    User(id=1, name="Ada Lovelace"),
    User(id=2, name="Grace Hopper"),
    User(id=3, name="Alan Turing"),
)

DEMO_PRODUCTS = (
    Product(id=1, name="Laptop Pro", price=1299.00),
    Product(id=2, name="Wireless Mouse", price=29.50),
    Product(id=3, name="USB-C Hub", price=49.00),
    Product(id=4, name="Laptop Stand", price=39.00),
)

DEMO_ORDERS = (
    Order(id=101, user_id=1, total=1328.50, status="shipped"),
    Order(id=102, user_id=2, total=49.00, status="processing"),
    Order(id=103, user_id=3, total=39.00, status="delivered"),
)

DEMO_REPORT = ReportResponse(
    title="Weekly summary",
    period="Last 7 days",
    rows=[
        ReportRow(label="Orders placed", value=128),
        ReportRow(label="Revenue", value=41250.75),
        ReportRow(label="New users", value=17),
    ],
)


def search_products(query: str) -> list[Product]:
    """Products whose name contains the query, ignoring case; everything if it is empty."""
    needle = query.strip().lower()
    return [product for product in DEMO_PRODUCTS if needle in product.name.lower()]


class UnknownProductError(ValueError):
    def __init__(self, index: int, product_id: int) -> None:
        super().__init__(f"Unknown product_id {product_id}")
        self.index = index
        self.product_id = product_id


def price_order(items: Sequence[OrderItem]) -> float:
    """Total price of the items. Raises UnknownProductError for a product that does not exist."""
    prices = {product.id: product.price for product in DEMO_PRODUCTS}
    total = 0.0
    for index, item in enumerate(items):
        if item.product_id not in prices:
            raise UnknownProductError(index, item.product_id)
        total += prices[item.product_id] * item.quantity
    return round(total, 2)
