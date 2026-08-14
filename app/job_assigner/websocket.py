from __future__ import annotations

import asyncio

from fastapi import WebSocket


class JobConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, tuple[str, bool]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, employee_code: str, can_view_all: bool
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = (employee_code, can_view_all)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    async def broadcast(
        self,
        event: dict,
        assigned_to: str | None = None,
        recipients: set[str] | None = None,
    ) -> None:
        async with self._lock:
            connections = list(self._connections.items())

        stale: list[WebSocket] = []
        for websocket, (employee_code, can_view_all) in connections:
            if recipients is not None:
                if employee_code not in recipients:
                    continue
            elif not can_view_all and employee_code != assigned_to:
                continue
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.pop(websocket, None)


job_connections = JobConnectionManager()
