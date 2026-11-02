"""Start the Boardroom Hub API:  python run.py   (http://localhost:5000, Swagger at /api/docs)."""
import os
import threading
import time

from app import create_app
from app.seed import seed_demo

app = create_app()


def reminder_loop():
    """Background job: send T-24h / T-1h reminders every 60 seconds."""
    from app.notify import send_due_reminders
    while True:
        time.sleep(60)
        try:
            with app.app_context():
                send_due_reminders()
        except Exception as exc:  # keep the loop alive
            app.logger.warning("reminder job failed: %s", exc)


if __name__ == "__main__":
    with app.app_context():
        if seed_demo():
            print("Demo data created – sign in with chair@boardroom.local / Password123!")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not os.environ.get("FLASK_DEBUG"):
        threading.Thread(target=reminder_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    print(f"API running on http://localhost:{port}  ·  Swagger UI: http://localhost:{port}/api/docs")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
