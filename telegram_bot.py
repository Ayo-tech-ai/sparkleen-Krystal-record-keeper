"""
Telegram Bot for Sparkling Crystal Dry Cleaning Record Keeper
Full agent integration - runs as a web service on Render
"""

import os
# ⚠️ CRITICAL: Set this BEFORE importing any ADK/Google modules
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

import asyncio
import csv
import io
import logging
import threading
from datetime import datetime, date
from typing import Optional

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import your existing modules
from core.database import init_db
from core.service import record_service
from agent.agent_setup import create_runner

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- FLASK APP ----------------

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Sparkling Crystal Record Keeper",
        "time": datetime.now().isoformat()
    })

@flask_app.route('/ping')
def ping():
    """Health check endpoint for UptimeRobot to keep the bot alive."""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    })

@flask_app.route('/health')
def health():
    """Detailed health check."""
    return jsonify({
        "status": "healthy",
        "bot_running": True,
        "timestamp": datetime.now().isoformat()
    })

# ---------------- CONFIG ----------------

DATABASE_NAME = "sparkling_crystal.db"
APP_NAME = "sparkling_crystal_app"
USER_ID = "telegram_user"

# Get tokens from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# ---------------- INITIALIZE SERVICES ----------------

# Initialize database
init_db()

# Create agent and runner
from agent.agent_setup import create_runner
runner, session_service = create_runner(app_name=APP_NAME)

# ---------------- SESSION MANAGEMENT ----------------

# Store user sessions (in-memory, consider Redis for production)
user_sessions = {}

def get_or_create_session(user_id: str):
    """Get or create a session for a Telegram user."""
    if user_id not in user_sessions:
        # Use sync method for simplicity
        session = session_service.create_session_sync(
            app_name=APP_NAME,
            user_id=user_id,
        )
        user_sessions[user_id] = session.id
    return user_sessions[user_id]

async def run_agent_turn(session_id: str, message: str) -> str:
    """Run one turn of the agent and return the response."""
    try:
        events = await runner.run_debug(
            message,
            user_id=USER_ID,
            session_id=session_id,
            quiet=True,
            verbose=False,
        )

        if not events:
            return "No response was generated."

        final_event = events[-1]

        # Check for receipt file in tool responses
        receipt_path = None
        for event in events:
            if hasattr(event, 'get_function_responses'):
                for fr in event.get_function_responses():
                    response_data = fr.response
                    if isinstance(response_data, dict) and response_data.get("receipt_file"):
                        receipt_path = response_data["receipt_file"]

        if final_event.content and final_event.content.parts:
            response = " ".join(
                part.text
                for part in final_event.content.parts
                if part.text
            )
            return response or "No response was generated."

        return "No response was generated."

    except Exception as e:
        error_str = str(e).lower()
        if "resourceexhausted" in error_str or "quota" in error_str or "rate" in error_str:
            return "I'm a bit busy right now (API limit reached). Please try again shortly."
        logger.error(f"Agent error: {e}")
        return f"Something went wrong on my end. Please try that again."

# ---------------- COMMAND HANDLERS ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    user_id = str(user.id)

    # Initialize session for this user
    get_or_create_session(user_id)

    welcome_message = f"""
✨ **Welcome to Sparkling Crystal Record Keeper, {user.first_name}!**

I'm your intelligent dry cleaning shop assistant. I help you manage customer drop-offs through natural conversation.

**What I can do:**
• 📝 Record customer drop-offs (with confirmation before saving)
• 💰 Track payments (full/partial/none)
• 📄 Generate professional PDF receipts
• 🔍 Search past records
• 📊 Export all records as CSV

**Just type naturally, like:**
• *"Mrs. Chioma brought 2 shirts for ₦1000, 3 trousers for ₦1200, paid ₦2000, collect on 25/07/2026"*
• *"Show me all records for Mrs. Chioma"*
• *"Resend receipt SC-20260723-001"*

**Quick Commands:**
/records - View recent records
/export_csv - Download all records as CSV
/help - Show all commands

Let's keep your shop organized! 💎
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    help_text = """
📋 **Available Commands:**

/start - Start the bot and get a welcome message
/help - Show this help message
/records - List recent records (optionally search by name or invoice)
/export_csv - Download all records as a CSV file

**Natural Language Examples:**

**Record a Drop-off:**
`Mrs. Chioma brought 2 shirts for ₦1000, 3 trousers for ₦1200, paid ₦2000, collect on 25/07/2026`

**Search Records:**
`Show me all records for Mrs. Chioma`
`Find invoice SC-20260723-001`

**Reprint Receipt:**
`Resend receipt SC-20260723-001`

I'll confirm before saving any drop-off - just chat with me! 💬
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def records_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent records or search by name/invoice."""
    try:
        query = " ".join(context.args) if context.args else None

        if query:
            # Try searching by customer name first
            results = record_service.search_records(customer_name=query)
            if not results:
                # If no results, try invoice number
                results = record_service.search_records(invoice_number=query)
        else:
            # Show last 10 records
            results = record_service.get_all_records()[:10]

        if not results:
            await update.message.reply_text(
                f"No records found for '{query}'." if query else "No records yet."
            )
            return

        lines = []
        for r in results[:10]:
            status_emoji = {
                "full": "✅",
                "partial": "⚠️",
                "none": "❌"
            }.get(r.get("payment_status", ""), "📄")
            
            lines.append(
                f"{status_emoji} **{r['invoice_number']}** — {r['customer_name']}\n"
                f"   ₦{r['total_amount']:,.0f} total | Balance: ₦{r['balance']:,.0f}\n"
                f"   📅 Drop-off: {r['dropoff_date']}"
            )

        response = "\n\n".join(lines)
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='Markdown')
        else:
            await update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Records error: {e}")
        await update.message.reply_text(f"⚠️ Error fetching records: {str(e)}")

async def export_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export all records as a CSV file."""
    try:
        all_records = record_service.get_all_records()

        if not all_records:
            await update.message.reply_text("📭 No records to export yet.")
            return

        # Flatten records for CSV
        flat_records = []
        for r in all_records:
            flat = {k: v for k, v in r.items() if k != "items"}
            flat["items_summary"] = "; ".join(
                f"{i['qty']}x {i['name']} (₦{i['amount']:,.0f})" 
                for i in r.get("items", [])
            )
            flat_records.append(flat)

        # Write to CSV
        output = io.StringIO()
        if flat_records:
            fieldnames = list(flat_records[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_records)

        # Convert to bytes for Telegram
        csv_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
        csv_bytes.seek(0)

        filename = f"sparkling_crystal_records_{date.today().isoformat()}.csv"

        await update.message.reply_document(
            document=csv_bytes,
            filename=filename,
            caption=f"📊 Sparkling Crystal Records Export — {len(all_records)} record(s) as of {date.today().isoformat()}"
        )

    except Exception as e:
        logger.error(f"Export CSV error: {e}")
        await update.message.reply_text(f"⚠️ Error exporting records: {str(e)}")

async def natural_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages using the agent."""
    user_message = update.message.text
    user_id = str(update.effective_user.id)

    # Get or create session for this user
    session_id = get_or_create_session(user_id)

    # Show typing indicator
    await update.message.chat.send_action(action="typing")

    try:
        # Run the agent
        response = await run_agent_turn(session_id, user_message)

        # Split long messages (Telegram limit is 4096 characters)
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

        # Check if receipt was generated (handled in run_agent_turn)
        # The agent will include the receipt file path in the response

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            f"⚠️ I encountered an error: {str(e)}\n\n"
            "Please try again or use /help for available commands."
        )

# ---------------- ERROR HANDLER ----------------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Oops! Something went wrong. Please try again or use /help for commands."
        )

# ---------------- RUN BOT ----------------

def run_bot():
    """Run the Telegram bot using polling."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("records", records_command))
    application.add_handler(CommandHandler("export_csv", export_csv_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_handler)
    )
    application.add_error_handler(error_handler)

    logger.info("🤖 Starting Sparkling Crystal Record Keeper Telegram Bot...")

    # Use polling - this manages its own event loop internally
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

# ---------------- RUN BOTH BOT AND WEB SERVER ----------------

if __name__ == "__main__":
    # Get port from environment (Render sets this)
    port = int(os.environ.get("PORT", 8080))

    # Run Flask in a separate thread
    def run_flask():
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"🌐 Web server running on port {port}")

    # Run the bot (this blocks, on the main thread, so signal handlers work fine)
    run_bot()
