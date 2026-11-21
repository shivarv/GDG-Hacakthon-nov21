# GDG Hackathon Nov 21: SentinelDesk

This repo holds several parts of the project. Each is documented below or in its own folder:

- **SentinelDesk triage & copilot** (`src/sentineldesk`, `app.py`, `scripts/`): see the first section below.
- **HelpDesk ticket system with email-to-case** (`backend/`, `frontend/`): see the second section below.
- **Clean dataset** (`dataset/`): see `dataset/README.md` and `dataset/METHODOLOGY.md`.
- **Triage models, kNN blend, urgency rules** (`triage/`), **data findings** (`findings/FINDINGS.md`), **Cloud Run service** (`deploy/`), **burst banner and dedup** (`live/`), **fused fine-tune experiments** (`exp/`).

---

# SentinelDesk: incident triage & grounded resolution copilot

For each helpdesk ticket (subject optional, English or German) SentinelDesk:

1. predicts **type, queue and priority** with calibrated confidence,
2. runs an **escalation and safety gate** (Auto-Draft Ready or Escalate to On-Call Engineer, with reasons),
3. retrieves the **top-5 most similar resolved tickets** (cross-lingual),
4. drafts a **reply in the requester's language** that cites the ticket IDs it used and never invents
   prices, refunds, SLA credits or legal guarantees.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # LLM_PROVIDER=none works without any API key
python scripts/build.py                                # split, train classifier, build FAISS index (~25 min CPU)
python scripts/build.py --max-kb 15000                 # faster build: index 15k tickets (classifier uses all)
python scripts/tune_gate.py                            # tune gate thresholds on a KB validation slice
python scripts/evaluate.py                             # holdout metrics -> artifacts/eval_report.json
streamlit run app.py                                   # console at http://localhost:8501
pytest -q                                              # 17 unit tests, no network or model download
```

**No dataset or artifacts?** `python scripts/demo.py` runs the pipeline on a 24-ticket built-in knowledge
base. `streamlit run app.py` falls back to the same demo knowledge base (with a visible warning) when
`artifacts/` is empty. Set `DEMO_MODE=1` to force it.

## Results (20% holdout, 12,353 tickets never seen in training or indexing)

| Metric | Value |
|---|---|
| Type Macro-F1 | 0.912 |
| Queue Macro-F1 | 0.921 |
| Priority Macro-F1 | 0.814 |
| High-priority recall (classifier alone) | 0.788 |
| High-priority Incident recall (classifier alone) | 0.757 |
| **Gate escalation recall on true high-priority incidents** | **0.939** |
| Auto-draft rate | 27% (the gate escalates when in doubt) |
| Latency p50 / p95 (classify + retrieve + draft) | 82 ms / 282 ms |

Gate figures come from a random 1,000-ticket holdout sample. Full report: `artifacts/eval_report.json`.
The dataset has five priority levels (`critical`, `high`, `medium`, `low`, `very_low`); `critical` is
treated as high for the gate and for high-priority recall.

## How it works

| Stage | Implementation |
|---|---|
| Classifier | word + char TF-IDF, one `LinearSVC(class_weight="balanced")` per target with sigmoid calibration |
| Language | `langdetect` with an en/de stop-word fallback |
| Retrieval | `multilingual-e5-small` + FAISS cosine (NumPy fallback), top-5. At least one hit from the other language is guaranteed when one exists, so a German ticket can use an English resolution |
| Gate | high/critical + Incident, incident-risk score, low classifier confidence, low retrieval similarity, critical-impact keywords, prompt injection, refund / pricing / SLA asks without supporting precedent, outage burst, draft guardrail failures |
| Reply | Claude or any OpenAI-compatible LLM returning strict JSON with citations; deterministic extractive fallback without a key |
| Guardrails | PII masked before any LLM call; citations to non-retrieved tickets removed; placeholders (`<name>`), money/credit sentences and weak precedents never quoted; unsupported numbers or commitment language flagged and escalated |
| Bonus | cross-lingual precedents, live outage-burst banner, PII guardrail |

## Zero data leakage

- `build.py` uses the brief's split: shuffle with seed 42, assign `TKT-xxxxx` IDs, first 80% is the KB.
  The classifier is trained on and the index built from the KB split only.
- `build.py` and `evaluate.py` assert that no holdout ticket ID is in the index.
- `evaluate.py` gives the pipeline only `subject` and `body` of holdout tickets. Labels stay aside for scoring.
- **Gate thresholds are tuned on a validation slice of the KB split** (`scripts/tune_gate.py`), never on the
  holdout. The holdout is used only to report final metrics.

## Configuration

All settings are environment variables read in `src/sentineldesk/config.py` (see `.env.example`).
Tuned gate thresholds live in `artifacts/gate_thresholds.json` (committed). A `SIM_THRESHOLD` env var
overrides the tuned similarity threshold.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `none` | `anthropic`, `openai` (any OpenAI-compatible endpoint, incl. Ollama/Groq) or `none` |
| `CONF_THRESHOLD` | `0.45` | escalate when any prediction is less confident |
| `MIN_OTHER_LANG` | `1` | cross-lingual hits guaranteed in the top-k |
| `BURST_SIM`, `BURST_MIN`, `BURST_WINDOW_MIN` | `0.88`, `3`, `15` | outage burst detection |

## Known limits

- The gate escalates about 73% of tickets. That is deliberate (a missed outage costs more than a false
  escalation). Lower `risk_threshold` in `gate_thresholds.json` to auto-draft more.
- Dataset answers are noisy, so extractive drafts (no LLM) can read awkwardly. An LLM provider gives
  fluent replies while the same citation and money guardrails apply. The real LLM path is covered by
  mocked unit tests only; it was not run against a live API.
- The queue label has about 50 classes, many unrelated to IT (for example Pets or Games).
- Burst detection uses similarity 0.88. Unrelated tickets peak near 0.87 with e5, so keep that value.
- The app runs locally. For a hosted demo, deploy `app.py` to Streamlit Community Cloud or any host and
  run `scripts/build.py` there first (or rely on the demo-mode fallback).

## Project structure

```
app.py                       Streamlit triage console
scripts/build.py             load -> clean -> 80/20 split -> train classifier -> build vector index
scripts/tune_gate.py         tune gate thresholds on a KB validation slice
scripts/evaluate.py          holdout metrics (Macro-F1, high-priority recall, gate recall, latency)
scripts/demo.py              dataset-free end-to-end demo
src/sentineldesk/            config, data, lang, pii, classifier, retriever, gate, generator, burst, pipeline, demo
tests/                       unit tests (no network, no model downloads)
```

## 5-minute demo script

1. **German, no subject**: language detected, German draft citing ticket IDs.
2. **Hospital VPN outage**: high-priority incident, escalation badge with reasons.
3. **Refund + SLA demand**: PII masked, escalated, the draft promises nothing.
4. **Prompt injection**: flagged and escalated.
5. **Outage simulation** (sidebar): three SSO tickets raise the major-incident banner.
6. Open "Holdout metrics" for Macro-F1, high-priority recall and latency.

---

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

To actually deliver, use **Brevo**. It's free for 300 emails a day and needs no domain.

**Quickest: Brevo API key.** If you already have a Brevo account with a verified sender, paste an API key (`xkeysib-…`, from **SMTP & API → API Keys**) into `backend/.env`. It takes priority over SMTP:
```
BREVO_API_KEY=xkeysib-...
SUPPORT_FROM_ADDRESS=<sender verified in that Brevo account>
```

**Or SMTP:**

1. Sign up at <https://www.brevo.com> on the Free plan.
2. **Settings → Senders, Domains & Dedicated IPs → Senders**: add a sender email you can read, then click the verification link Brevo sends.
3. **Settings → SMTP & API → SMTP**: copy the **Login** and click **Generate a new SMTP key**.
4. In `backend/.env`, set:
   ```
   SMTP_ENABLED=true
   SMTP_USERNAME=<Brevo SMTP login>
   SMTP_PASSWORD=<Brevo SMTP key>
   SUPPORT_FROM_ADDRESS=<the sender you verified>
   ```
   The host (`smtp-relay.brevo.com`), port (587) and TLS are already set.
5. Restart the backend and use **Send test** on the Email channel page. Check the spam folder too.

Reply-To is the live mail.tm inbox, so customer replies come back into the helpdesk. Gmail SMTP with an App Password also works; see the comments in `.env.example`.

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

All backend settings live in `backend/.env`. It's gitignored; start from `backend/.env.example`. By default the backend uses a SQLite file at `backend/.data/helpdesk.db` and a free public mail.tm inbox, so nothing else needs to be installed.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in the Brevo values to send real email
uvicorn app.main:app --reload --reload-include .env   # restarts when code or .env changes

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev     # http://localhost:5173
```

To use Postgres instead, run `docker compose up db` and set
`DATABASE_URL=postgresql+psycopg://helpdesk:helpdesk@localhost:5432/helpdesk`.

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
