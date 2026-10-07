# Backend architecture

The backend keeps its existing technical layers and divides each layer by
ownership:

- `auth` contains ESS-side authentication and application behavior.
- `sdk` contains the external browser SDK and client-authentication flow.
- `shared` contains infrastructure used by both sides.

```text
app/
├── api/endpoints/{auth,sdk}/
├── schemas/{auth,sdk,shared}/
├── services/{auth,sdk,shared}/
├── models/{auth,sdk,shared}/
├── core/{auth,sdk,shared}/
└── main.py
```

## Dependency rules

1. Auth modules must not import SDK modules.
2. SDK modules may reuse auth employee and face-verification services. They
   must not duplicate that business logic.
3. Shared modules must not import auth or SDK modules.
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
- Database sessions and audit infrastructure belong in `core/shared/`.
- A future SDK WebSocket protocol belongs under SDK endpoints and services;
  it should not be implemented inside an auth application service.
