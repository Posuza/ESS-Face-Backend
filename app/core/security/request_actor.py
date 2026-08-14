from __future__ import annotations

import re

from fastapi import HTTPException, Request

EMPLOYEE_CODE_PATTERN = re.compile(r"^\d{6}$")


def extract_actor_employee_code(request: Request) -> str:
    code_from_header = (
        request.headers.get("x-employee-code")
        or request.headers.get("x-user-code")
        or request.headers.get("x-actor-code")
    )
    if code_from_header and EMPLOYEE_CODE_PATTERN.fullmatch(code_from_header.strip()):
        return code_from_header.strip()

    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token_value = auth[7:].strip()
        # Current app uses simple employee code tokens in dev.
        if EMPLOYEE_CODE_PATTERN.fullmatch(token_value):
            return token_value

    raise HTTPException(
        status_code=401,
        detail="Missing actor identity. Provide X-Employee-Code header or Bearer <employee_code>.",
    )
