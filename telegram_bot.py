import os
import asyncio
from datetime import date

import pandas as pd
from flask import Flask, request

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from core.database import init_db
from core.service import record_service
from agent.agent_setup import create_runner

# ---------------- SETUP ----------------

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]  # e.g. https://your-app.onrender.com
WEBHOOK_PATH = "/webhook"

init_db()

flask_app = Flask(__name__)
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Each Telegram chat gets its own isolated agent session
runner, session_service = create_runner(app_name="sparkling_crystal_telegram")
chat_sessions = {}  # chat_id -> session object


async def get_or_create_session(chat_id):
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = await session_service.create_session(
            app_name="sparkling_crystal_telegram",
            user_id=str(chat_id)
        )
    return chat_sessions[chat_id]


# ---------------- COMMAND HANDLERS ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Sparkleen Krystal Record Keeper.\n\n"
        "Describe a drop-off in your own words and I'll help you record it, "
        "generate a receipt, and keep track of your customers.\n\n"
        "Type /help to see everything I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Here's what I can help with:\n\n"
        "• Just tell me about a drop-off, e.g. \"Mrs. Chioma brought 2 shirts "
        "for 1000, paid 2000, collect on 25/07/2026\" — I'll confirm before saving.\n"
        "• Ask me to search records, e.g. \"show me Chioma's records\"\n"
        "• Ask me to resend a receipt, e.g. \"resend SC-20260723-001\"\n\n"
        "Commands:\n"
        "/export_csv — download all records as a CSV file\n"
        "/records [name or invoice] — list recent records, or filter by name/invoice\n"
        "/help — show this message"
    )


async def export_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_records = record_service.get_all_records()

    if not all_records:
        await update.message.reply_text("No records yet.")
        return

    flat_records = []
    for r in all_records:
        flat = {k: v for k, v in r.items() if k != "items"}
        flat["items_summary"] = "; ".join(
            f"{i['qty']}x {i['name']} (₦{i['amount']:,.0f})" for i in r["items"]
        )
        flat_records.append(flat)

    df = pd.DataFrame(flat_records)
    filename = f"/tmp/sparkleen_krystal_records_{date.today().isoformat()}.csv"
    df.to_csv(filename, index=False)

    with open(filename, "rb") as f:
        await update.message.reply_document(document=f, filename=os.path.basename(filename))


async def records_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None

    if query:
        results = record_service.search_records(customer_name=query)
        if not results:
            results = record_service.search_records(invoice_number=query)
    else:
        results = record_service.get_all_records()[:10]

    if not results:
        await update.message.reply_text(f"No records found for '{query}'." if query else "No records yet.")
        return

    lines = []
    for r in results:
        lines.append(
            f"📄 {r['invoice_number']} — {r['customer_name']}\n"
            f"   ₦{r['total_amount']:,.0f} total | Balance: ₦{r['balance']:,.0f} | {r['payment_status']}\n"
            f"   Dropped off: {r['dropoff_date']}"
        )

    await update.message.reply_text("\n\n".join(lines))


# ---------------- NATURAL LANGUAGE CHAT ----------------

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_text = update.message.text

    session = await get_or_create_session(chat_id)

    try:
        events = await runner.run_debug(
            user_text,
            user_id=str(chat_id),
            session_id=session.id,
            quiet=True,
            verbose=False
        )

        final_event = events[-1]

        receipt_path = None
        for event in events:
            if event.get_function_responses():
                for fr in event.get_function_responses():
                    response_data = fr.response
                    if isinstance(response_data, dict) and response_data.get("receipt_file"):
                        receipt_path = response_data["receipt_file"]

        if final_event.content and final_event.content.parts:
            reply_text = " ".join(part.text for part in final_event.content.parts if part.text)
        else:
            reply_text = "No response was generated."

        await update.message.reply_text(reply_text)

        if receipt_path:
            with open(receipt_path, "rb") as f:
                await update.message.reply_document(document=f, filename=os.path.basename(receipt_path))

    except Exception as e:
        error_str = str(e).lower()
        if "resourceexhausted" in error_str or "quota" in error_str or "rate" in error_str:
            await update.message.reply_text("I'm a bit busy right now (API limit reached). Please try again shortly.")
        else:
            await update.message.reply_text("Something went wrong on my end. Please try that again.")


# ---------------- REGISTER HANDLERS ----------------

telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("export_csv", export_csv_command))
telegram_app.add_handler(CommandHandler("records", records_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))


# ---------------- FLASK ROUTES ----------------

@flask_app.route("/", methods=["GET"])
def health_check():
    return "Sparkleen Krystal Telegram Bot is running.", 200


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok", 200


# ---------------- STARTUP: set the webhook once ----------------

async def set_webhook():
    await telegram_app.bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}")


if __name__ == "__main__":
    asyncio.run(telegram_app.initialize())
    asyncio.run(set_webhook())

    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
