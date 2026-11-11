from app.core.logging import configure_logging
from app.db.session import SessionLocal, get_engine
from app.services.seed import seed_all
from app.services.storage import ensure_bucket


def main() -> None:
    configure_logging()
    get_engine()
    ensure_bucket()
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
