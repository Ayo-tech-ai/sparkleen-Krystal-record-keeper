import os
from datetime import date

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

from agent.tools import record_dropoff, search_records, get_receipt_for_invoice
from agent.skills import record_keeper_core_skill, record_keeper_operations_skill

today_str = date.today().isoformat()

# Wrap tool functions
record_dropoff_tool = FunctionTool(record_dropoff)
search_records_tool = FunctionTool(search_records)
get_receipt_for_invoice_tool = FunctionTool(get_receipt_for_invoice)

# Bundle skills into a toolset
record_keeper_toolset = SkillToolset(
    skills=[
        record_keeper_core_skill,
        record_keeper_operations_skill,
    ],
    additional_tools=[]
)

record_keeper_agent = Agent(

    model="gemini-3.5-flash",

    name="sparkling_crystal_record_keeper",

    description=(
        "A focused AI record keeper for a dry cleaning shop — handles "
        "drop-off intake, payment tracking, receipt generation, and "
        "record search."
    ),

    instruction=f"""
You are the Sparkleen Krystal Record Keeper.

You are the single point of interaction for the shop owner.

Today's date is {today_str}. Resolve any relative date the owner
mentions into an exact YYYY-MM-DD date BEFORE calling any tool.

Your responsibility is to help manage drop-off records using the
available Skills and Tools behind the scenes.

GENERAL RULES

- Never expose internal implementation details.
- Never mention Skills, Tool calls, or FunctionTools.
- Never invent customer names, items, amounts, or dates.
- Treat the shop's records as the single source of truth.
- Stay strictly on-task — no general conversation.

- To record a confirmed drop-off and generate its receipt, call
  record_dropoff directly. Always available. NEVER call this before
  the owner has explicitly confirmed the intake summary.
- To search past records, call search_records directly.
  Always available.
- To reprint or resend a receipt, call get_receipt_for_invoice
  directly. Always available.

- Load the record-keeper-operations skill to guide how you handle
  intake, confirmation, saving, and search.
- Load the record-keeper-core skill to guide your identity, tone,
  and strict scope boundaries.

- Never simulate tool execution. Wait for tool results before
  responding.
- If required information is missing, ask only for the missing
  information.

Maintain a professional, efficient tone — accurate above all else.
""",

    tools=[
        record_dropoff_tool,
        search_records_tool,
        get_receipt_for_invoice_tool,
        record_keeper_toolset,
    ]
)


def _session_db_url() -> str:
    """Builds the SQLAlchemy URL ADK's DatabaseSessionService needs.

    Falls back to SUPABASE_DB_URL so you only need ONE env var.
    The +psycopg driver prefix is required by SQLAlchemy.
    Keepalive params stop Supabase's pooler dropping idle connections.
    """
    url = os.environ.get("ADK_SESSION_DB_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError(
            "SUPABASE_DB_URL (or ADK_SESSION_DB_URL) is not set. "
            "Agent session memory needs a database to survive restarts."
        )
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    sep = "&" if "?" in url else "?"
    url += f"{sep}keepalives=1&keepalives_idle=60&keepalives_interval=30&keepalives_count=5"
    return url


def create_runner(app_name="sparkling_crystal_app"):
    """Creates a runner backed by Supabase Postgres for session state.

    Session memory now survives Render restarts/spin-downs because it is
    persisted in the database, not in process memory.
    """
    session_service = DatabaseSessionService(db_url=_session_db_url())
    runner = Runner(
        app_name=app_name,
        agent=record_keeper_agent,
        session_service=session_service
    )
    return runner, session_service
