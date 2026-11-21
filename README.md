# HelpDesk — Ticket Management with Email-to-Case

A ticket management system where emails sent to the support inbox automatically become cases.

- **Backend:** Python, FastAPI, SQLAlchemy 2, PostgreSQL, organised as controller → service → DAO layers
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, built from small modular components
- **Email:** an IMAP listener plus an inbound webhook, both converting emails into cases
- **Infra:** Docker Compose (Postgres, backend, frontend/nginx, GreenMail as the dev mail server)

## Quick start

```bash
docker compose up --build
```

| Service      | URL                          |
|--------------|------------------------------|
| Frontend     | http://localhost:3000        |
| API docs     | http://localhost:8000/docs   |
| SMTP (dev)   | localhost:3025               |
| IMAP (dev)   | localhost:3143               |

### Try the email-to-case flow

```bash
# New email -> new case (priority auto-detected from "Urgent")
python backend/scripts/send_test_email.py

# Reply -> threaded onto case TCK-1 as a comment (a resolved case reopens)
python backend/scripts/send_test_email.py --subject "Re: [TCK-1] cannot log in" --body "Still broken"
```

Within about 10 seconds the listener picks the email up, and the case appears under **Tickets** and **Email Inbox**.
You can also use the **Simulate inbound email** panel on the Email Inbox page, which calls the webhook directly.

## How email becomes a case

```
 Customer email ──► Mailbox (IMAP) ──► ImapEmailListener ─┐
                                                          ├─► EmailIngestionService
 Provider webhook ──► POST /api/emails/inbound ───────────┘          │
                                                                     ▼
                         Is it a duplicate Message-ID? ── yes ──► ignore (idempotent)
                                       │ no
                         Does the subject carry [TCK-n], or does In-Reply-To match a known email?
                              │ yes                                │ no
                              ▼                                    ▼
                  Add a comment (quoted text stripped);  Create a ticket (source=email,
                  reopen the case if resolved/closed     priority detected from keywords)
                                                                   │
                                                                   ▼
                                               Send an acknowledgement with [TCK-n]
                                               in the subject so replies thread back
```

Every inbound email is stored in `email_messages` along with its outcome (`created_ticket`, `appended_comment` or `failed`) for auditing.

## Backend layout

```
backend/app/
├── main.py                  # App factory, CORS, error handler, starts the IMAP listener
├── core/                    # config (env settings), database session, exceptions
├── models/                  # SQLAlchemy entities: Ticket, Comment, EmailMessage
├── schemas/                 # Pydantic request/response DTOs
├── dao/                     # Data access only (queries); flushes, never commits
├── services/                # Business logic and transaction boundaries
│   ├── ticket_service.py
│   ├── comment_service.py
│   ├── email_ingestion_service.py   # email -> case logic
│   ├── email_parser.py              # RFC 822 parsing, quote stripping, priority detection
│   └── notification_service.py      # SMTP acknowledgements
├── controllers/             # FastAPI routers (HTTP only), with services injected through Depends
└── email_listener/          # IMAP polling background thread
```

### API

| Method | Path                               | Description                          |
|--------|------------------------------------|--------------------------------------|
| GET    | `/api/tickets`                     | List tickets (`status`, `priority`, `source`, `q`, `page`, `page_size`) |
| POST   | `/api/tickets`                     | Create a ticket                      |
| GET    | `/api/tickets/stats`               | Counts by status, priority and source |
| GET    | `/api/tickets/{id}`                | Ticket with its comments             |
| PATCH  | `/api/tickets/{id}`                | Update status, priority, assignee and other fields |
| DELETE | `/api/tickets/{id}`                | Delete a ticket                      |
| POST   | `/api/tickets/{id}/comments`       | Add a reply or internal note         |
| GET    | `/api/tickets/{id}/emails`         | Emails linked to a ticket            |
| GET    | `/api/emails`                      | Inbound email log                    |
| POST   | `/api/emails/inbound`              | Inbound-email webhook                |

## Frontend layout

```
frontend/src/
├── api/          # fetch client plus tickets and emails endpoints
├── types/        # Shared TypeScript types
├── hooks/        # useAsync, useTickets, useEmails
├── components/
│   ├── common/   # Button, Badge, Card, Select, Pagination, Spinner, ...
│   ├── layout/   # AppLayout, Sidebar, MobileNav, PageHeader
│   ├── tickets/  # TicketTable, TicketFilters, TicketForm, CommentList, ...
│   ├── dashboard/# StatCard, BreakdownBar
│   └── emails/   # EmailTable, InboundEmailSimulator
├── pages/        # Dashboard, Tickets, TicketDetail, NewTicket, Emails
└── utils/
```

## Local development without Docker

```bash
# Database and mail server only
docker compose up db mail

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev     # http://localhost:5173
```

## Using a real mailbox

Set these variables in `.env` (or in `docker-compose.yml`):

```
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USE_SSL=true
IMAP_USERNAME=support@yourcompany.com
IMAP_PASSWORD=<app password>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=support@yourcompany.com
SMTP_PASSWORD=<app password>
```

Alternatively, point your email provider's inbound-parse webhook at `POST /api/emails/inbound`.

## Notes

- Tables are created on startup with `create_all`. For production schema changes, add Alembic.
- There is no authentication yet. Add it before exposing the app publicly.
