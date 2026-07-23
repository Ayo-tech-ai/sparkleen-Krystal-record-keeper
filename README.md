# 🧺 Sparkleen Krystal Record Keeper

An AI-powered record keeper built for **Sparkleen Krystal Dry Cleaning Shop** (Warri, Delta State). It replaces manual notebook record-keeping with a focused AI agent that captures customer drop-offs through natural conversation, tracks payments, calculates late fees, and generates professional PDF receipts — all backed by a searchable, exportable database.

Built with **Google ADK** and **Gemini 3.6 Flash**.

---

## Why This Exists

Dry cleaning shops typically track drop-offs on paper or in ad-hoc notebooks — error-prone, hard to search, and offering customers no proof of what they dropped off. This system solves that with:

- Natural-language intake ("Mrs. Chioma brought 2 shirts for ₦1,000...") instead of manual form-filling
- A mandatory confirm-before-save step, so the AI never records something it misheard
- Instant, professional PDF receipts
- Automatic 15% late fee calculation on overdue balances
- A searchable record of every drop-off, by customer, invoice number, date, or payment status
- One-click CSV export of the full record history

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
├── core/                    # Framework-agnostic business logic
│   ├── database.py          # SQLite connection + schema
│   ├── helpers.py           # WAT timestamps, invoice number generation, type coercion
│   ├── service.py           # RecordKeeperService — all DB read/write logic
│   └── receipt.py           # PDF receipt generation (fpdf2)
├── agent/                   # Google ADK agent layer
│   ├── tools.py             # FunctionTools exposed to the agent
│   ├── skills.py            # Identity/tone skill + operations logic skill
│   └── agent_setup.py       # Agent, tool, and runner assembly
├── data/                    # SQLite database file (gitignored)
└── receipts/                # Generated PDF receipts (gitignored)
```

**Design principle:** `core/` contains zero AI-specific code — it's plain Python business logic that could be reused with any framework. `agent/` is where Google ADK, the LLM, and tool-calling live. This separation keeps the record-keeping logic testable and independent of the AI layer.

### Data Flow

```
User (chat/Telegram) → Agent parses intent → Structured summary shown
    → User confirms → record_dropoff tool called → RecordKeeperService
    writes to SQLite → generate_receipt produces PDF → Response + receipt returned
```

### Database Schema

Single table, `dropoff_records`:

| Field | Type | Notes |
|---|---|---|
| `invoice_number` | TEXT | Format: `SC-YYYYMMDD-NNN`, sequential per day |
| `customer_name` | TEXT | |
| `items` | TEXT (JSON) | Array of `{name, qty, amount}` |
| `total_units`, `total_amount` | INTEGER, REAL | Computed from items |
| `payment_status` | TEXT | `full` / `partial` / `none` |
| `amount_paid`, `balance` | REAL | |
| `service_type` | TEXT | Wash & Iron / Wash Only / Iron Only |
| `dropoff_date`, `collection_date` | DATE | |
| `created_at` | TIMESTAMP | WAT (UTC+1) |

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
| Language Model | Gemini 3.6 Flash |
| Database | SQLite |
| PDF Generation | fpdf2 |
| Web Interface | Streamlit |
| Chat Interface | Telegram Bot |
| Deployment | Streamlit Community Cloud (dashboard) + Render (bot) |

---

## Running Locally

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd sparkleen-krystal-record-keeper
pip install -r requirements.txt
```

**2. Add your Gemini API key**

Create `.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY = "your-gemini-api-key"
```

**3. Run the app**

```bash
streamlit run app.py
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

---

## About This Project

Sparkleen Krystal Record Keeper is a personal project built to run my own dry cleaning business, Sparkleen Krystal, in Warri, Nigeria — and to demonstrate practical, production-oriented AI agent design: structured tool use, confirm-before-write safety patterns, and multi-surface deployment (web dashboard + chat bot) sharing a single source of truth.

Built by **Ay** — AI developer, educator, and consultant.
