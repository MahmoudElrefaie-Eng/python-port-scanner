"""The provider extension point every vulnerability data source implements."""

from __future__ import annotations

from typing import Protocol

from port_scanner.security.models import Vulnerability


class VulnerabilityProvider(Protocol):
    """A source of vulnerability data — a local cache, a live API, or
    anything else that can answer "what CVEs affect this product?".

    Structural typing (a `Protocol`, not an ABC to subclass) so a new
    provider only needs to match this shape, not import or depend on
    anything in this module.
    """

    name: str

    def lookup(self, product: str, version: str | None) -> list[Vulnerability]:
        """Vulnerabilities known to affect `product` at `version`.

        `version` may be `None` (product identified, version unknown) —
        implementations should still return whatever they reasonably can
        (e.g. product-level matches) rather than nothing.

        Must never raise: a provider failure (network error, malformed
        response, anything) should be caught internally and reported as
        "no results", not propagated — see DECISIONS.md 32.
        """
        ...
