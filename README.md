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

### Email in from Gmail (no domain needed)

With `TEMP_INBOX_ENABLED=true` (on by default in Docker Compose), the backend creates a free public address
through [mail.tm](https://mail.tm), such as `helpdesk-1a2b3c4d@<mail.tm domain>`, and shows it in a banner on the
**Email Inbox** page. Send an email to it from Gmail or any mail app and it becomes a case within about 10 seconds.
Replying in the same Gmail thread adds a comment to that case.

- Receive-only: nothing is ever sent through mail.tm.
- The address is saved to `.data/temp_inbox.json` and reused on restart. Delete that file to get a new address.
- mail.tm is a public third-party service. Use it for demos, not for sensitive data.

```bash
# Run locally without Docker (SQLite, temp inbox on)
cd backend
DATABASE_URL=sqlite:///./dev.db TEMP_INBOX_ENABLED=true uvicorn app.main:app
```

## How email becomes a case

```
 Customer email ──► Mailbox (IMAP) ──► ImapEmailListener ─┐
 Gmail ──► mail.tm temp address ──► TempInboxListener ─────┤
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

## Escalations

Any ticket that is open, in progress or pending can be escalated from the ticket list (the siren button) or the ticket page.

- You pick an **escalation contact** and give a reason. The ticket is reassigned to them, an internal note is added, and they are emailed.
- **Levels:** team leads are L2. Managers, on-call and security are L3. Escalating again moves the ticket up a level and closes the previous escalation.
- **Closing:** resolving or closing the ticket closes its escalation automatically. You can also de-escalate by hand.
- **Auto-assign (default):** the dialog suggests a contact and explains why.
  - **Team:** from topic keywords in English and German, e.g. invoice/refund → Billing, outage/"is down" → on-call, phishing/breach → Security, login/password → Technical Support.
  - **Level:** L2 by default. L3 for urgent tickets, re-escalations, and outage or security topics.
  - **Workload:** the least-loaded contact wins.

  `GET /api/tickets/{id}/escalation-suggestion` returns the pick, the reasons and a preview of the customer email.
- **Customer handoff email:** the requester is told who is now handling their ticket, with that person's email and phone. The subject keeps the `[TCK-n]` tag and Reply-To points at the inbox the system reads, so replies thread back onto the ticket.
- **Dummy contacts:** 9 escalation contacts plus 2 frontline agents are loaded on first start (`backend/app/core/seed.py`). They all use the non-routable `@helpdesk.local` domain and fictional `+1 555-01xx` phone numbers.
- **Storage:** "Escalated" is calculated from the `escalations` table, so no migration of `tickets` is needed. The `source` field (`manual` or `auto`) is reserved for the SentinelDesk escalation gate.

## Outgoing email (sending to Gmail and other real inboxes)

Every outbound email is logged in `outbound_emails` and shown under **Email channel → Outbound** as `sent`, `skipped` (SMTP off) or `failed`. That covers acknowledgements, escalation notices and customer handoffs.

To actually deliver, use a Gmail account as the support sender:

1. Turn on 2-Step Verification for that Google account.
2. Create an App Password at <https://myaccount.google.com/apppasswords>.
3. Fill in `backend/.env`, which is gitignored:
   ```
   SMTP_ENABLED=true
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USERNAME=your.support@gmail.com
   SMTP_PASSWORD=<16-character app password>
   ```
4. Restart the backend and use **Send test** on the Email channel page.

Emails are sent *from* the Gmail account, since Gmail rejects other From addresses. Reply-To is the live support inbox when the temp inbox is enabled.

## Backend layout

```
backend/app/
├── main.py                  # App factory, CORS, error handler, starts the IMAP listener
├── core/                    # config (env settings), database session, exceptions
├── models/                  # SQLAlchemy entities: Ticket, Comment, EmailMessage, User, Escalation
├── schemas/                 # Pydantic request/response DTOs
├── dao/                     # Data access only (queries); flushes, never commits
├── services/                # Business logic and transaction boundaries
│   ├── ticket_service.py
│   ├── comment_service.py
│   ├── escalation_service.py        # escalate / re-escalate / de-escalate + notify
│   ├── escalation_routing_service.py # auto-assign: topic → team, level, least-loaded contact
│   ├── email_ingestion_service.py   # email -> case logic
│   ├── email_parser.py              # RFC 822 parsing, quote stripping, priority detection
│   └── notification_service.py      # all outbound email (SMTP) + outbound log
├── controllers/             # FastAPI routers (HTTP only), with services injected through Depends
└── email_listener/          # Background pollers: IMAP mailbox and mail.tm temp inbox
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
| POST   | `/api/tickets/{id}/escalate`       | Escalate an open ticket to a contact (`escalated_to_id`, `reason`, `reassign`) |
| POST   | `/api/tickets/{id}/de-escalate`    | Close the active escalation          |
| GET    | `/api/tickets/{id}/escalations`    | Escalation history for a ticket      |
| GET    | `/api/escalations`                 | Escalations across tickets (`status=active|resolved`) |
| GET    | `/api/users`                       | Support staff (`escalation_contacts=true` for escalation targets) |
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
