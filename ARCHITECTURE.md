# Backend architecture

The backend keeps its existing technical layers and divides each layer by
ownership:

- `main` contains the ESS application's own behavior.
- `sdk` contains the external browser SDK and client-authentication flow.
- `shared` contains infrastructure used by both sides.

```text
app/
├── api/endpoints/{main,sdk}/
├── schemas/{main,sdk,shared}/
├── services/{main,sdk,shared}/
├── models/{main,sdk,shared}/
├── core/{main,sdk,shared}/
└── main.py
```

## Dependency rules

1. Main modules must not import SDK modules.
2. SDK modules may reuse main employee and face-verification services. They
   must not duplicate that business logic.
3. Shared modules must not import main or SDK modules.
4. HTTP endpoints validate input and delegate behavior to services.
5. Schemas contain API contracts only; ORM models contain persistence only.
6. `app/main.py` remains the FastAPI entrypoint and does not contain feature
   behavior.
7. Moving a module must not change an API URL, response contract, table name,
   or SDK public method.

## Placement examples

- A normal employee login belongs in `services/main/auth.py`.
- Ticket verification and logout auditing belong in `services/sdk/auth.py`.
- Client registration persistence belongs in `models/sdk/`.
- Database sessions and audit infrastructure belong in `core/shared/`.
- A future SDK WebSocket protocol belongs under SDK endpoints and services;
  it should not be implemented inside a main application service.
