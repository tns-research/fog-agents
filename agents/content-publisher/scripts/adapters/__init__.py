"""Publishing adapters of content-publisher, one interface for every provider.

    from adapters import get_adapter
    adapter = get_adapter("dry-run")

See base.py for the interface and scripts/README.md for each adapter's setup.
"""

from __future__ import annotations

from typing import Dict, Type

from .base import Adapter, ProviderError, ProviderUnavailable, neutral_payload  # noqa: F401
from .command import CommandAdapter
from .dry_run import DryRunAdapter
from .webhook import WebhookAdapter
from .zernio import ZernioAdapter

ADAPTERS: Dict[str, Type[Adapter]] = {
    DryRunAdapter.name: DryRunAdapter,
    ZernioAdapter.name: ZernioAdapter,
    CommandAdapter.name: CommandAdapter,
    WebhookAdapter.name: WebhookAdapter,
}


def get_adapter(name: str) -> Adapter:
    if name not in ADAPTERS:
        raise ProviderUnavailable(f"unknown adapter {name!r}: one of {', '.join(sorted(ADAPTERS))}")
    return ADAPTERS[name]()
