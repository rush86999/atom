
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atom.db")

# Optimization: Connection Pooling
# For SQLite, we use StaticPool for in-memory or simple file-based access
# For PostgreSQL (production), we would use QueuePool with specific settings
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connection before usage
    pool_recycle=3600,   # Recycle connections every hour
    echo=False           # Disable SQL logging for performance
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with get_db_session() as db:
    try:
        yield db
    finally:
        db.close()
