"""
Clear all calls from the database (and optionally from storage). Use for dev/reset only.

  docker-compose exec api python scripts/clear_all_calls.py
  docker-compose exec api python scripts/clear_all_calls.py --db-only   # skip storage cleanup
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import Call

def main():
    parser = argparse.ArgumentParser(description="Clear all calls (dev only)")
    parser.add_argument("--db-only", action="store_true", help="Only delete from DB, skip storage")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        calls = db.query(Call).all()
        if not calls:
            print("No calls to clear.")
            return
        if not args.db_only:
            try:
                from services.storage import get_storage_service
                storage = get_storage_service()
                for c in calls:
                    try:
                        storage.delete_file(c.s3_path)
                    except Exception as e:
                        print(f"Warning: could not delete file {c.s3_path}: {e}")
            except Exception as e:
                print(f"Warning: storage cleanup skipped: {e}")
        for c in calls:
            db.delete(c)
        db.commit()
        print(f"Cleared {len(calls)} call(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
