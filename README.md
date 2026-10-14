# 🧺 Sparkleen Krystal Record Keeper

An AI-powered record keeper built for **Sparkleen Krystal Dry Cleaning Shop** (Warri, Delta State). It replaces manual notebook record-keeping with a focused AI agent that captures customer drop-offs through natural conversation, tracks payments, calculates late fees, and generates professional PDF receipts — all backed by a persistent, searchable, exportable cloud database.

Built with **Google ADK** and **Gemini 3.5 Flash**.

---

## Why This Exists

Dry cleaning shops typically track drop-offs on paper or in ad-hoc notebooks — error-prone, hard to search, and offering customers no proof of what they dropped off. This system solves that with:

- Natural-language intake ("Mrs. Chioma brought 2 shirts for ₦1,000...") instead of manual form-filling
- A mandatory confirm-before-save step, so the AI never records something it misheard
- Instant, professional PDF receipts
- Automatic 15% late fee calculation on overdue balances
- A searchable record of every drop-off, by customer, invoice number, date, or payment status
- One-click CSV export of the full record history
- Cloud persistence — records and agent memory survive restarts, redeploys, and platform spin-downs

---

## How It Works

1. **Describe a drop-off** — via the chat interface or Telegram: items, quantities, prices, payment made, and collection date.
2. **Review the summary** — the AI echoes back exactly what it understood: items, totals, amount paid, balance due, collection date.
3. **Confirm** — only after explicit confirmation does it save the record and generate the receipt. It never saves on the first message.
4. **Get the receipt** — a professional ¼-A4 PDF receipt, ready to print or send.

The AI is intentionally narrow in scope — it does not hold general conversation. It exists to do one job well: keep accurate shop records.

---

## Architecture

```
sparkleen-krystal-record-keeper/
├── app.py                   # Streamlit app — manual entry form, search, CSV export, chat
├── telegram_bot.py          # Telegram bot (Flask health server + polling, runs on Render)
├── core/                    # Framework-agnostic business logic
│   ├── database.py          # Supabase Postgres connection + schema (psycopg)
│   ├── helpers.py           # WAT timestamps, invoice number generation, type coercion
│   ├── service.py           # RecordKeeperService — all DB read/write logic
│   └── receipt.py           # PDF receipt generation (fpdf2)
├── agent/                   # Google ADK agent layer
│   ├── tools.py             # FunctionTools exposed to the agent
│   ├── skills.py            # Identity/tone skill + operations logic skill
│   └── agent_setup.py       # Agent, tool, and runner assembly (Postgres-backed sessions)
├── data/                    # Local scratch dir (receipt PDFs land here; gitignored)
└── receipts/                # Generated PDF receipts (gitignored)
```

**Design principle:** `core/` contains zero AI-specific code — it's plain Python business logic that could be reused with any framework. `agent/` is where Google ADK, the LLM, and tool-calling live. This separation keeps the record-keeping logic testable and independent of the AI layer.

### Data Flow

```
User (chat/Telegram) → Agent parses intent → Structured summary shown
    → User confirms → record_dropoff tool called → RecordKeeperService
    writes to Supabase Postgres → generate_receipt produces PDF
    → Response + receipt returned
```

Agent conversation state (session memory) is persisted per-turn in Supabase
via ADK's `DatabaseSessionService`, so an in-progress intake survives
container restarts — the bot can be redeployed mid-conversation and still
remember the pending summary.

### Database Schema

Single table, `dropoff_records` (created automatically on first run):

| Field | Type | Notes |
|---|---|---|
| `invoice_number` | TEXT | Format: `SC-YYYYMMDD-NNN`, sequential per day |
| `customer_name` | TEXT | |
| `items` | TEXT (JSON) | Array of `{name, qty, amount}` |
| `total_units`, `total_amount` | INTEGER, DOUBLE PRECISION | Computed from items |
| `payment_status` | TEXT | `full` / `partial` / `none` |
| `amount_paid`, `balance` | DOUBLE PRECISION | |
| `service_type` | TEXT | Wash & Iron / Wash Only / Iron Only |
| `dropoff_date`, `collection_date` | DATE | |
| `late_fee_applied` | BOOLEAN | Default FALSE |
| `created_at` | TIMESTAMP | WAT (UTC+1) |

ADK additionally manages its own `sessions` / `events` tables in the same
database for agent memory.

### Late Fee Logic

Applied only at receipt-generation time, only shown as a final figure (never the breakdown):

```
late_fee = balance × 15%
total_due = balance + late_fee
displayed_amount = round(total_due to nearest ₦100)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Framework | Google Agent Development Kit (ADK) |
| Language Model | Gemini 3.5 Flash |
| Database | Supabase Postgres (psycopg) |
| Agent Session Store | ADK `DatabaseSessionService` (same Supabase Postgres) |
| PDF Generation | fpdf2 |
| Web Interface | Streamlit |
| Chat Interface | Telegram Bot (python-telegram-bot) |
| Bot Web Server | Flask (health endpoints) |
| Keep-alive | UptimeRobot pinging `/ping` |
| Deployment | Streamlit Community Cloud (dashboard) + Render free tier (bot) |

**Why Supabase:** Render's free tier containers are ephemeral — anything
stored in process memory or local disk vanishes on spin-down. All durable
state (records + agent sessions) lives in Supabase Postgres instead, so the
compute layer is fully replaceable: the same repo can be redeployed anywhere
with zero data loss.

---

## Configuration

The app reads three environment variables:

| Variable | Where | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | Render env, Streamlit secrets, local `.env` | Gemini API access |
| `TELEGRAM_TOKEN` | Render env only | Telegram Bot API token |
| `SUPABASE_DB_URL` | Render env, Streamlit secrets | Postgres connection string (enables both records and session memory) |

**Supabase connection string:** Project Settings → Database →
Connection String → use the **transaction pooler** URI (port `6543`) on
hosts without IPv6 (e.g., Render). `agent_setup.py` automatically adapts
this URL for ADK's session service (`postgresql+psycopg://` prefix).

**Streamlit secrets** (`.streamlit/secrets.toml` locally, or the app's
Secrets settings on Streamlit Cloud):

```toml
GOOGLE_API_KEY = "your-gemini-api-key"
SUPABASE_DB_URL = "postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
```

**Render environment:** set `TELEGRAM_TOKEN`, `GOOGLE_API_KEY`, and
`SUPABASE_DB_URL` in the service's Environment settings, then redeploy.
Add a free [UptimeRobot](https://uptimerobot.com) monitor on
`https://<your-app>.onrender.com/ping` (every 10 min) to prevent the free
tier from spinning down.

---

## Running Locally

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd sparkleen-krystal-record-keeper
pip install -r requirements.txt
```

**2. Add your secrets**

Create `.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY = "your-gemini-api-key"
SUPABASE_DB_URL = "postgresql://..."
```

For the Telegram bot locally, also export the token:

```bash
export TELEGRAM_TOKEN="your-telegram-bot-token"
```

**3. Run the web app**

```bash
streamlit run app.py
```

**4. Run the Telegram bot**

```bash
python telegram_bot.py
```

---

## Features

- ✅ Natural-language drop-off intake with mandatory confirmation before saving
- ✅ Manual entry form (no AI required, for fast direct input)
- ✅ Automatic invoice numbering (`SC-YYYYMMDD-NNN`)
- ✅ Payment tracking — full, partial, or no payment, with live balance calculation
- ✅ Automatic 15% late fee calculation, rounded to the nearest ₦100
- ✅ Professional ¼-A4 PDF receipts, generated instantly
- ✅ Search by customer name, invoice number, date, or payment status
- ✅ Full record history exportable to CSV
- ✅ Strict on-task scope — the AI does not engage in general conversation
- ✅ Telegram bot for on-the-go record keeping
- ✅ Persistent cloud database — records survive restarts, redeploys, and free-tier spin-downs
- ✅ Persistent agent memory — in-progress drop-off intake survives bot restarts
- ✅ One database shared by both surfaces — records entered on Telegram appear in the web app instantly

---

## About This Project

Sparkleen Krystal Record Keeper is a personal project built to run my own dry cleaning business, Sparkleen Krystal, in Warri, Nigeria — and to demonstrate practical, production-oriented AI agent design: structured tool use, confirm-before-write safety patterns, persistent session state, and multi-surface deployment (web dashboard + chat bot) sharing a single cloud source of truth.

Built by **Ay** — AI developer, educator, and consultant.
