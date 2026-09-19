"""Verify the pure helpers behind the demo routes."""

import pytest

from app.schemas.demo import OrderItem, Product
from app.services.demo_data import UnknownProductError, price_order, search_products


def item(product_id: int, quantity: int = 1) -> OrderItem:
    return OrderItem(product_id=product_id, quantity=quantity)


def test_an_order_total_is_price_times_quantity_summed() -> None:
    assert price_order([item(2, 2), item(3, 1)]) == 108.0  # 29.50 * 2 + 49.00


def test_the_same_product_on_two_lines_is_added_up() -> None:
    assert price_order([item(2), item(2, 3)]) == 118.0


def test_totals_are_rounded_to_cents(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.1 * 3 is 0.30000000000000004 in floating point; the total must come out as 0.3."""
    monkeypatch.setattr(
        "app.services.demo_data.DEMO_PRODUCTS", (Product(id=1, name="x", price=0.1),)
    )
    assert price_order([item(1, 3)]) == 0.3


def test_an_unknown_product_reports_its_position() -> None:
    with pytest.raises(UnknownProductError) as error:
        price_order([item(2), item(99)])
    assert (error.value.index, error.value.product_id) == (1, 99)


def test_search_ignores_case_and_surrounding_spaces() -> None:
    assert [p.id for p in search_products("  LAPTOP ")] == [1, 4]
