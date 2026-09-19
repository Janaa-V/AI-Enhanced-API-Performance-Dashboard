"""Verify the shared error format and how failures are documented."""

import pytest

from app.api.errors import ERROR_DETAILS, error_detail, error_responses
from app.schemas.errors import ErrorResponse
from app.services.simulation import DEFAULT_PROFILES


def test_every_status_a_profile_can_return_has_a_specific_error_detail() -> None:
    """Adding a new failure status to a profile forces a decision about its error code."""
    used = {s for profile in DEFAULT_PROFILES.values() for s in profile.failure_statuses}
    assert used <= set(ERROR_DETAILS)


def test_error_codes_are_distinct_and_machine_friendly() -> None:
    codes = [detail.code for detail in ERROR_DETAILS.values()]
    assert len(codes) == len(set(codes))
    assert all(code.islower() and " " not in code for code in codes)


def test_unmapped_statuses_get_a_generic_but_valid_detail() -> None:
    assert error_detail(502).code == "server_error"


def test_error_responses_document_each_status_once_in_order() -> None:
    documented = error_responses([503, 500, 503])
    assert list(documented) == [500, 503]
    assert documented[503]["model"] is ErrorResponse


@pytest.mark.parametrize("status", [500, 503, 504])
def test_the_documented_message_matches_the_returned_message(status: int) -> None:
    assert error_responses([status])[status]["description"] == error_detail(status).message
