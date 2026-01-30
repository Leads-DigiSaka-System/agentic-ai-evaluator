"""
Seed Langfuse dashboard with demo trace (user_id + session_id).

Run once to see data in Sessions and Users tabs:
  uv run python scripts/seed_langfuse_demo.py

Requires .env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (optional).
"""
import sys
from pathlib import Path

# Project root
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from dotenv import load_dotenv
load_dotenv(root / ".env")

from src.monitoring.trace.langfuse_helper import (
    initialize_langfuse,
    get_langfuse_client,
    flush_langfuse,
    get_trace_url,
    get_current_trace_id,
)


def main():
    if not initialize_langfuse():
        print("Langfuse not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
        sys.exit(1)

    client = get_langfuse_client()
    if not client:
        print("Could not get Langfuse client.")
        sys.exit(1)

    user_id = "demo_user"
    session_id = "demo_session"

    with client.start_as_current_observation(as_type="span", name="seed_demo_trace") as span:
        client.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            tags=["demo", "seed", "script"],
            metadata={"source": "seed_langfuse_demo.py"},
        )
        span.update(
            input={"message": "Demo trace from seed script", "user_id": user_id, "session_id": session_id},
            output={"status": "ok"},
        )
        trace_id = get_current_trace_id()
        url = get_trace_url()

    flush_langfuse()
    print("Done. Trace sent to Langfuse.")
    if trace_id:
        print(f"  Trace ID: {trace_id}")
    if url:
        print(f"  URL: {url}")
    print(f"  User: {user_id}  |  Session: {session_id}")
    print("Check dashboard: Sessions and Users tabs should show demo_user / demo_session.")


if __name__ == "__main__":
    main()
