from __future__ import annotations

import ipaddress
import re
from urllib.parse import SplitResult, urlsplit


class InvalidCallbackUrl(ValueError):
    """Raised when a client callback URL is not a safe absolute web URL."""


_LOOPBACK_NAMES = {"localhost"}


def _parsed_web_url(value: str) -> SplitResult:
    raw = value.strip()
    if not raw or "\\" in raw or any(ord(character) < 32 for character in raw):
        raise InvalidCallbackUrl("Callback URL is invalid.")

    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidCallbackUrl("Callback URL must use HTTP or HTTPS.")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise InvalidCallbackUrl("Callback URL must contain a valid host.")
    try:
        parsed.port
    except ValueError as exc:
        raise InvalidCallbackUrl("Callback URL contains an invalid port.") from exc
    return parsed


def _normalized_host(hostname: str) -> tuple[str, bool]:
    host = hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise InvalidCallbackUrl("Callback URL contains an invalid host.") from exc
        labels = host.split(".")
        if (
            not re.fullmatch(r"[a-z0-9.-]+", host)
            or any(not label or len(label) > 63 for label in labels)
            or any(label.startswith("-") or label.endswith("-") for label in labels)
        ):
            raise InvalidCallbackUrl("Callback URL contains an invalid host.")
        return host, host in _LOOPBACK_NAMES

    return str(address), address.is_loopback


def _origin(parsed: SplitResult) -> str:
    scheme = parsed.scheme.lower()
    host, is_loopback = _normalized_host(parsed.hostname or "")
    if scheme == "http" and not is_loopback:
        raise InvalidCallbackUrl("Non-loopback callback URLs must use HTTPS.")

    display_host = f"[{host}]" if ":" in host else host
    port = parsed.port
    if port is None or (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return f"{scheme}://{display_host}"
    return f"{scheme}://{display_host}:{port}"


def normalize_allowed_origin(value: str) -> str:
    """Normalize a configured origin and reject paths, queries, and fragments."""

    parsed = _parsed_web_url(value)
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise InvalidCallbackUrl("Allowed callback origin must not contain a path, query, or fragment.")
    return _origin(parsed)


def callback_origin(value: str) -> str:
    """Return the canonical origin for an absolute callback URL."""

    return _origin(_parsed_web_url(value))


def callback_matches_origin(value: str, allowed_origin: str | None) -> bool:
    if not allowed_origin:
        return False
    try:
        return callback_origin(value) == normalize_allowed_origin(allowed_origin)
    except InvalidCallbackUrl:
        return False
