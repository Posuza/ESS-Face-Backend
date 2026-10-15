from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from app.services.sdk.auth import client_auth_service


_logger = logging.getLogger("uvicorn.error")


@dataclass
class ClientPresence:
    connection_id: str
    app_name: str
    public_key: str
    client_ip: str
    origin: str
    user_agent: str
    employee_id: str
    device_id: str
    latitude: float | None
    longitude: float | None
    connected_at: datetime
    last_seen_at: datetime


class ClientPresenceService:
    """In-memory current SDK presence for one backend process.

    Heartbeats update only ``last_seen_at``. They do not create database rows
    or log entries; this service is for live monitoring, not audit history.
    """

    def __init__(self) -> None:
        self._connections: dict[str, ClientPresence] = {}
        self._subscribers: set[asyncio.Queue[None]] = set()
        self._last_heartbeat_broadcast = 0.0

    def subscribe(self) -> asyncio.Queue[None]:
        """Subscribe to coalesced live-state changes without holding a DB session."""
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        queue.put_nowait(None)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[None]) -> None:
        self._subscribers.discard(queue)

    def publish_update(self) -> None:
        """Wake each monitor once; a slow monitor never accumulates heartbeats."""
        for queue in tuple(self._subscribers):
            if queue.empty():
                queue.put_nowait(None)

    def connect(
        self,
        db: Session,
        public_key: str,
        client_ip: str,
        origin: str,
        user_agent: str,
        employee_id: str,
        device_id: str,
        request: HTTPConnection,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> ClientPresence:
        app = client_auth_service.registered_application_for_callback(
            db,
            public_key,
            origin,
            request,
        )
        presence = ClientPresence(
            connection_id=secrets.token_urlsafe(12),
            app_name=app.app_name,
            public_key=app.public_key,
            client_ip=client_ip,
            origin=origin,
            user_agent=user_agent,
            employee_id=employee_id,
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            connected_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        self._connections[presence.connection_id] = presence
        _logger.info(
            "SDK presence connected app=%s public_key=%s ip=%s origin=%s "
            "employee=%s device=%s latitude=%s longitude=%s user_agent=%s "
            "connections=%d clients=%d devices=%d users=%d",
            presence.app_name,
            presence.public_key,
            presence.client_ip,
            presence.origin or "unknown",
            presence.employee_id,
            presence.device_id,
            presence.latitude if presence.latitude is not None else "unknown",
            presence.longitude if presence.longitude is not None else "unknown",
            presence.user_agent or "unknown",
            self.active_count(presence.public_key),
            self.active_client_count(presence.public_key),
            self.active_device_count(presence.public_key),
            self.active_user_count(presence.public_key),
        )
        self.publish_update()
        return presence

    def heartbeat(
        self,
        connection_id: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> ClientPresence | None:
        presence = self._connections.get(connection_id)
        if presence:
            presence.last_seen_at = datetime.now(timezone.utc)
            location_changed = False
            if latitude is not None and longitude is not None:
                location_changed = (
                    presence.latitude != latitude
                    or presence.longitude != longitude
                )
                presence.latitude = latitude
                presence.longitude = longitude
                if location_changed:
                    _logger.info(
                        "SDK presence location app=%s employee=%s device=%s "
                        "latitude=%.6f longitude=%.6f",
                        presence.app_name,
                        presence.employee_id,
                        presence.device_id,
                        latitude,
                        longitude,
                    )
            now = time.monotonic()
            if location_changed or now - self._last_heartbeat_broadcast >= 1.0:
                self._last_heartbeat_broadcast = now
                self.publish_update()
        return presence

    def disconnect(self, connection_id: str) -> None:
        presence = self._connections.pop(connection_id, None)
        if not presence:
            return
        _logger.info(
            "SDK presence disconnected app=%s public_key=%s ip=%s "
            "employee=%s device=%s latitude=%s longitude=%s "
            "connections=%d clients=%d devices=%d users=%d",
            presence.app_name,
            presence.public_key,
            presence.client_ip,
            presence.employee_id,
            presence.device_id,
            presence.latitude if presence.latitude is not None else "unknown",
            presence.longitude if presence.longitude is not None else "unknown",
            self.active_count(presence.public_key),
            self.active_client_count(presence.public_key),
            self.active_device_count(presence.public_key),
            self.active_user_count(presence.public_key),
        )
        self.publish_update()

    def active_count(self, public_key: str) -> int:
        return sum(
            presence.public_key == public_key
            for presence in self._connections.values()
        )

    def active_device_count(self, public_key: str) -> int:
        return len({
            presence.device_id
            for presence in self._connections.values()
            if presence.public_key == public_key
        })

    def active_client_count(self, public_key: str) -> int:
        return len({
            (presence.employee_id, presence.device_id)
            for presence in self._connections.values()
            if presence.public_key == public_key
        })

    def active_user_count(self, public_key: str) -> int:
        return len({
            presence.employee_id
            for presence in self._connections.values()
            if presence.public_key == public_key
        })

    def snapshot(self) -> dict:
        """Return the current live state for the Super Admin monitor."""
        connections = sorted(
            self._connections.values(),
            key=lambda item: item.connected_at,
            reverse=True,
        )
        applications: dict[str, dict] = {}
        for presence in connections:
            app = applications.setdefault(
                presence.public_key,
                {
                    "app_name": presence.app_name,
                    "public_key": presence.public_key,
                    "connections": 0,
                    "employees": set(),
                    "devices": set(),
                    "clients": set(),
                },
            )
            app["connections"] += 1
            app["employees"].add(presence.employee_id)
            app["devices"].add(presence.device_id)
            app["clients"].add((presence.employee_id, presence.device_id))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "connections": len(connections),
                "applications": len(applications),
                "employees": len({item.employee_id for item in connections}),
                "devices": len({item.device_id for item in connections}),
                "clients": len(
                    {
                        (item.public_key, item.employee_id, item.device_id)
                        for item in connections
                    }
                ),
            },
            "applications": [
                {
                    "app_name": app["app_name"],
                    "public_key": app["public_key"],
                    "connections": app["connections"],
                    "employees": len(app["employees"]),
                    "devices": len(app["devices"]),
                    "clients": len(app["clients"]),
                }
                for app in sorted(applications.values(), key=lambda item: item["app_name"])
            ],
            "connections": [
                {
                    "connection_id": item.connection_id,
                    "app_name": item.app_name,
                    "public_key": item.public_key,
                    "employee_id": item.employee_id,
                    "device_id": item.device_id,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "client_ip": item.client_ip,
                    "user_agent": item.user_agent,
                    "connected_at": item.connected_at.isoformat(),
                    "last_seen_at": item.last_seen_at.isoformat(),
                }
                for item in connections
            ],
        }


client_presence_service = ClientPresenceService()
