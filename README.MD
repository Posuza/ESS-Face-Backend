# ESS MO Backend verson3

This is the backend API for the ESS MO (Employee Self Service - Ministry of Organization) system. It is built with Python (FastAPI), providing secure RESTful endpoints for employee management, attendance, reporting, and more.

## Features
- Employee and department management
- Attendance and shift tracking
- Role-based access control
- Audit logging
- Modular, extensible architecture

## Development Guide

Backend modules are separated into `auth` and `sdk` ownership folders. Shared
core infrastructure stays in `core/shared`; small cross-cutting modules remain
at their layer root. See [ARCHITECTURE.md](ARCHITECTURE.md) before adding
endpoints, schemas, services, models, or core infrastructure.

### Prerequisites
- Python 3.9 or newer
- (Recommended) Virtual environment tool: `venv`, `virtualenv`, or `conda`
- PostgreSQL or MySQL database (or adjust `.env` for your DB)

### Clone and Run

```bash
# Clone the repository
 git clone https://github.com/Posuza/ESS_MO_Backend.git
 cd ESS_MO_Backend

# Create and activate a virtual environment
 python -m venv venv
 source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
 pip install -r requirements.txt

# Copy and edit your .env file
 cp .env.example .env
 # Edit .env with your DB and secret settings

# Run the API server
 uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000` by default.

### Client application tickets

Create the client-application table once for the configured database:

```bash
python scripts/create_auth_app_registry_table.py
```

Existing installations using the previous table name can preserve their rows
and rename it in place:

```bash
python scripts/rename_auth_app_registry_table.py
```

Existing registries must add the callback-origin column once:

```bash
python scripts/add_auth_app_callback_origin.py
```

Add administrator attribution and the shared callback IP-block table:

```bash
python scripts/add_auth_app_audit_columns.py --backfill-employee-code ADMIN_CODE
python scripts/create_auth_callback_ip_limits_table.py
```

Assign an origin to an existing production registration:

```bash
python scripts/set_auth_app_callback_origin.py PUBLIC_KEY https://client.example.com
```

Super Admins register an application name and one exact callback origin with
`POST /api/v1/admin/client-applications`. HTTPS is required except for loopback
development origins. Any callback path is accepted only when its parsed scheme,
host, and port match the registered origin. The response returns the generated public
key as a mandatory 16-character URL-safe identifier; the private key never
leaves this backend. Keys with any other length are rejected. Ticket lifetime is controlled
globally by `CLIENT_TICKET_TTL_SECONDS` (30 seconds by default). Password or
face login can issue an encrypted ticket through
`/api/v1/client-auth/tickets/password` or `/api/v1/client-auth/tickets/face`.
Client SDKs verify it through `/api/v1/client-auth/tickets/verify`, which returns
only `employee_id`. Redirect handling belongs to the client application. The
SDK reports browser logout to `POST /api/v1/client-auth/logout` with the client
public key and verified employee ID so ESS can validate both and write an audit
entry. This notification does not create or revoke a server session.

Rejected callback origins are audited by source IP. Ten failures within five
minutes block that IP for fifteen minutes by default. The block is stored in
the database so it applies across workers and survives restarts. Configure the
policy with `CALLBACK_MAX_FAILED_ATTEMPTS`, `CALLBACK_FAILURE_WINDOW_SECONDS`,
and `CALLBACK_IP_BLOCK_SECONDS`. Only addresses in `TRUSTED_PROXY_IPS` may
supply the client IP through `X-Forwarded-For`.

For presence testing, the browser SDK opens
`/api/v1/client-auth/presence/ws?public_key=...`. The backend logs when the
client connects, sends a heartbeat, or disconnects, including the source IP,
origin, and user agent. WebSocket origins must match the origin registered for
the public key. Presence is diagnostic only and is not authorization.

### Import employee JSON data into MySQL

Set `DB_ENGINE=mysql` and the target `DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD`, and `DB_NAME` values in `.env`. Then run:

```powershell
venv\Scripts\python.exe scripts\import_employee_json_to_mysql.py
```

The importer creates the application schema and imports employee master data,
MO transactions, and MO report jobs from `jsons/headers` and `jsons/data`. It
refuses to write into non-empty target tables. To deliberately delete and
replace that selected data, run it with `--replace` after backing up MySQL.

### Deployment
- Authentication and recovery services record attempts and outcomes for password
  login, face verification, email recovery, face recovery, and password changes.
  Face enrollment and administrator face replacement/removal record the target
  employee and actor code; client application list/create/update/delete actions
  also produce audit events. Passwords, tickets, private keys, and image payloads
  are not included in these events. Employee identities on unauthenticated
  attempts describe the account being attempted, not proof of authentication.
  Browser-only validation and requests rejected before service execution are
  outside this service-level audit coverage.
- Backend startup safely creates the `auth_app_registry` and
  `auth_callback_ip_limits` tables when an upgraded database does not have
  them yet. Existing tables and rows are preserved.
- See `/deployment` for Windows service deployment (NSSM/Servy) and production configuration.
- For Linux, use a process manager like `systemd` or `supervisord`.
- Set `--host 0.0.0.0` and configure your reverse proxy (Nginx, Caddy, etc.) for production.

---

For more details, see the `/deployment` folder and code documentation.
