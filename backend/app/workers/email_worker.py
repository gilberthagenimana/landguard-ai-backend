
"""Dedicated background worker for notification email delivery."""

import logging
import signal
from threading import Event

from app.db.session import SessionLocal
from app.services.notification.dispatcher import dispatch_pending_deliveries

POLL_INTERVAL_SECONDS = 15
BATCH_SIZE = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
stop_event = Event()


def request_shutdown(signum, frame):
    logger.info("Shutdown signal received. Finishing current batch...")
    stop_event.set()


def run_worker():
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    logger.info("LandGuard email worker started.")


    while not stop_event.is_set():
        attempted = 0
        db = SessionLocal()

        try:
            attempted = dispatch_pending_deliveries(
                db,
                limit=BATCH_SIZE,
            )

            if attempted:
                logger.info("Attempted delivery of %s email(s).", attempted)

        except Exception:
            db.rollback()
            logger.exception("Email worker encountered an error.")

        finally:
            db.close()

        if stop_event.is_set():
            break

        if attempted >= BATCH_SIZE:
            continue

        stop_event.wait(POLL_INTERVAL_SECONDS)

    logger.info("LandGuard email worker stopped.")


if __name__ == "__main__":
    run_worker()
