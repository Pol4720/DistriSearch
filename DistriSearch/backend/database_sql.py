from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Activity
import os

SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///./distrisearch_users.db")

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_activity(db: SessionLocal, user_id: int, action: str, details: str):
    activity = Activity(user_id=user_id, action=action, details=details)
    db.add(activity)
    db.commit()