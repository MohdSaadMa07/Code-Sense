import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    DATA_DIR = Path(__file__).resolve().parent / "data"
    DATA_DIR.mkdir(exist_ok=True)
    engine = create_engine(f"sqlite:///{DATA_DIR / 'codesense.db'}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_migrations():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "conversations" in tables:
        cols = [c["name"] for c in inspector.get_columns("conversations")]
        if "repo_url" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN repo_url VARCHAR(512) NOT NULL DEFAULT ''"))
                conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
