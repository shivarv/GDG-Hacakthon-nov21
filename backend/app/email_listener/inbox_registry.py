"""Holds the live public inbox address (if any) so outbound mail can set Reply-To
to an address the system actually reads — customer replies then thread back."""

_address: str | None = None


def set_inbox_address(address: str | None) -> None:
    global _address
    _address = address


def get_inbox_address() -> str | None:
    return _address
