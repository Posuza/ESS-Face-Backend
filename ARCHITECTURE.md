# Backend architecture

The backend keeps its existing technical layers and divides each layer by
ownership:

- `auth` contains ESS-side authentication and application behavior.
- `sdk` contains the external browser SDK and client-authentication flow.
- Root-level layer modules hold small cross-cutting concerns such as audit
  persistence.
- `core/shared` contains substantial infrastructure used by both sides.

```text
app/
├── api/endpoints/{auth,sdk}/
├── schemas/{auth,sdk}/
├── services/{auth,sdk}/
├── models/{auth,sdk}/
├── core/{auth,sdk,shared}/
└── main.py
```

## Dependency rules

1. Auth modules must not import SDK modules.
2. SDK modules may reuse auth employee and face-verification services. They
   must not duplicate that business logic.
3. Root-level cross-cutting modules and `core/shared` must not import auth or
   SDK modules.
4. HTTP endpoints validate input and delegate behavior to services.
5. Schemas contain API contracts only; ORM models contain persistence only.
6. `app/main.py` remains the FastAPI entrypoint and does not contain feature
   behavior.
7. Moving a module must not change an API URL, response contract, table name,
   or SDK public method.

## Placement examples

- A normal employee login belongs in `services/auth/auth.py`.
- Ticket verification and logout auditing belong in `services/sdk/auth.py`.
- Client registration persistence belongs in `models/sdk/`.
- Audit persistence remains at the root of `models`, `schemas`, and `services`
  until it grows enough to justify a dedicated folder.
- Database sessions and audit infrastructure belong in `core/shared/`.
- A future SDK WebSocket protocol belongs under SDK endpoints and services;
  it should not be implemented inside an auth application service.

## SDK presence testing

`/api/v1/client-auth/presence/ws` maintains a lightweight WebSocket connection
for a registered client public key. The backend logs connection, heartbeat, and
disconnection events together with the source IP, origin, user agent, and the
current active connection count.

Presence is diagnostic and must not authorize users. IP and user-agent values
are network metadata, not verified identity attributes. The active registry is
in memory and therefore valid only for the current single-process test server;
a multi-worker deployment requires a shared presence store such as Redis.

## SDK callback trust

Each client registration owns one normalized callback origin. External login is
allowed only when the parsed `return_to` scheme, host, and port match that
origin; paths and query strings may vary within it. Ticket issuance repeats the
check, and SDK WebSocket connections apply the same rule to the browser
`Origin`. HTTP callback origins are restricted to loopback development clients.
Rejected callback attempts are recorded in the audit log. Their source-IP
failure counters and temporary blocks are shared through
`auth_callback_ip_limits`, not browser storage. A rejected origin may return
only to the registered application origin with an SDK error marker; a blocked
IP receives `429` and no client redirect.
