from __future__ import annotations

import base64
import hashlib
import json
import time

from cryptography.fernet import Fernet, InvalidToken


class InvalidClientTicket(ValueError):
    """Raised when a client ticket is malformed, expired, or cannot be verified."""


def _cipher(private_key: str) -> Fernet:
    derived_key = hashlib.sha256(private_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def issue_client_ticket(
    employee_id: str,
    private_key: str,
    *,
    current_time: int | None = None,
) -> str:
    payload = json.dumps(
        {"employee_id": employee_id},
        separators=(",", ":"),
    ).encode("utf-8")
    issued_at = int(time.time()) if current_time is None else current_time
    return _cipher(private_key).encrypt_at_time(payload, issued_at).decode("ascii")


def verify_client_ticket(
    ticket: str,
    private_key: str,
    ttl_seconds: int,
    *,
    current_time: int | None = None,
) -> str:
    now = int(time.time()) if current_time is None else current_time
    try:
        plaintext = _cipher(private_key).decrypt_at_time(
            ticket.encode("ascii"),
            ttl=ttl_seconds,
            current_time=now,
        )
        payload = json.loads(plaintext)
        employee_id = payload["employee_id"]
    except (InvalidToken, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise InvalidClientTicket("Invalid or expired client ticket.") from exc

    if not isinstance(employee_id, str) or not employee_id:
        raise InvalidClientTicket("Invalid or expired client ticket.")
    return employee_id
