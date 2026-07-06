"""Shared helpers: payment options and Bazaar extension builder.

For search-term tuning (tags, service name, icon), see ``discovery_config.py``.
"""
from typing import Any

from x402.extensions.bazaar import OutputConfig, declare_discovery_extension
from x402.http import PaymentOption


def make_payment_option(
    pay_to: str, network: str, price: str
) -> PaymentOption:
    """Create a standard USDC payment option (exact scheme)."""
    return PaymentOption(
        scheme="exact",
        pay_to=pay_to,
        price=price,
        network=network,
    )


def make_bazaar_extension(
    input_example: dict[str, Any],
    input_schema: dict[str, Any],
    output_example: dict[str, Any],
) -> dict[str, Any]:
    """Build a Bazaar discovery extension dict.

    Wraps the SDK's ``declare_discovery_extension`` and patches the
    required ``method`` field that the SDK omits at declaration time.
    """
    ext = declare_discovery_extension(
        input=input_example,
        input_schema=input_schema,
        output=OutputConfig(example=output_example),
    )
    # SDK startup validation requires 'method' in info.input
    ext["bazaar"]["info"]["input"]["method"] = "GET"
    return ext
