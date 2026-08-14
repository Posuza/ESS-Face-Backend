# ESS MO Backend

This is the backend API for the ESS MO (Employee Self Service - Ministry of Organization) system. It is built with Python (FastAPI), providing secure RESTful endpoints for employee management, attendance, reporting, and more.

## Features
- Employee and department management
- Attendance and shift tracking
- Role-based access control
- Audit logging
- Modular, extensible architecture

## Development Guide

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
- See `/deployment` for Windows service deployment (NSSM/Servy) and production configuration.
- For Linux, use a process manager like `systemd` or `supervisord`.
- Set `--host 0.0.0.0` and configure your reverse proxy (Nginx, Caddy, etc.) for production.

---

For more details, see the `/deployment` folder and code documentation.
