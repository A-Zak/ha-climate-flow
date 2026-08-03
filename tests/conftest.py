"""Fixtures for Climate Flow tests."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Iterator[None]:
    """Enable loading custom integrations in tests."""
    yield
