"""
Mark calls stuck in 'processing' for too long as failed.
Usage:
  docker-compose exec api python scripts/mark_stuck_calls_failed.py
  docker-compose exec api python scripts/mark_stuck_calls_failed.py --hours 6
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import Call, ProcessingJob


def main():
    hours = float(os.environ.get("STUCK_HOURS", "2"))
    if "--hours" in sys.argv:
        i = sys.argv.index("--hours")
        if i + 1 < len(sys.argv):
            hours = float(sys.argv[i + 1])
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    db = SessionLocal()
    try:
        stuck = db.query(Call).filter(
            Call.status == "processing",
            Call.processing_started_at.isnot(None),
            Call.processing_started_at < cutoff,
        ).all()
        if not stuck:
            print(f"No calls stuck in 'processing' for > {hours} hour(s).")
            return
        msg = f"Marked failed: processing exceeded {hours} hour(s) (stuck)."
        for call in stuck:
            call.status = "failed"
            call.error_message = msg
            in_progress = db.query(ProcessingJob).filter(
                ProcessingJob.call_id == call.call_id,
                ProcessingJob.status == "in_progress",
            ).all()
            for job in in_progress:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                job.error_message = msg
        db.commit()
        print(f"Marked {len(stuck)} call(s) as failed: {[c.call_id for c in stuck]}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
