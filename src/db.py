from __future__ import annotations
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os


# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./manga_pipeline.db')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PipelineRun(Base):
    """Database model for tracking pipeline runs."""
    __tablename__ = "pipeline_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)  # Celery task ID
    manga_title = Column(String, index=True)
    chapter_number = Column(Float)
    language = Column(String)
    status = Column(String, default='pending')  # pending, started, scraping, summarizing, etc.
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    

# Create tables
Base.metadata.create_all(bind=engine)


def get_db_session():
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise