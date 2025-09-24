# FHIR Patient Portal Backend

This repository provides a Django REST Framework implementation of the FHIR Patient Portal backend featuring Role-Based Access Control (RBAC), comprehensive CRUD endpoints, validations, and tooling to accelerate development.

## Features

- Django REST Framework API with JWT authentication via SimpleJWT.
- Role-Based Access Control with default roles (ADMIN, MANAGER, STAFF, PATIENT, VIEWER).
- CRUD endpoints for patients, observations, appointments, notifications, analytics, audit logging, and more.
- HL7 ingestion service with batch processing endpoints.
- Telemedicine session, consent, and metrics APIs.
- Analytics endpoints for risk scores and machine learning lifecycle management.
- Structured error payloads and OpenAPI documentation powered by drf-spectacular.
- Postman collection for quick end-to-end testing.

## Getting Started

### Prerequisites

- Python 3.11+
- MySQL 8.x (or use SQLite for quick local testing)
- `pip`

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template and adjust the values as needed:

```bash
cp .env.example .env
```

If you are not ready to connect to MySQL, leave the database variables empty to fall back to SQLite (default behaviour).

### Database Setup

Run the migrations and seed the default RBAC roles:

```bash
python manage.py migrate
python manage.py roles_seed --admin-email admin@example.com --admin-password ChangeMe123!
```

### Running the Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/`. Visit `/api/docs/` for the interactive OpenAPI documentation.

### Postman Collection

Import the `postman_collection.json` file into Postman. The collection includes:

- Auth folder (`/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`)
- Admin folder for role management
- Folder per entity with CRUD examples and validation test scripts

Update the `BASE_URL`, `ACCESS_TOKEN`, and `REFRESH_TOKEN` variables in the collection environment to match your environment.

### User Registration

End users can self-register by sending a `POST` request to `/api/auth/register/` with their contact details, strong password, and
acceptance of the terms of service. The endpoint enforces password complexity (mixed case, number, special character), requires
matching password confirmation, validates phone and birthdate formats, and ensures email uniqueness before creating the account.
Successful registrations are automatically assigned the `PATIENT` role and linked profile metadata for downstream RBAC checks.

## Testing

Run the included unit tests:

```bash
python manage.py test
```

## Makefile Helpers

The repository includes a `Makefile` with shortcuts:

- `make init` – Install dependencies and set up the environment
- `make migrate` – Apply database migrations
- `make seed-roles` – Seed default roles
- `make run` – Run the development server

## Docker Compose (Optional)

A `docker-compose.yml` file is included to orchestrate the Django app alongside a MySQL database for local development. Update environment variables as needed before running:

```bash
docker-compose up --build
```

## License

This project is provided as-is for demonstration purposes.
