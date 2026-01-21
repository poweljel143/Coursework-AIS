from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/autosalon")

# Add UTF-8 encoding to the database URL if not present
if "charset" not in DATABASE_URL:
    if "?" in DATABASE_URL:
        DATABASE_URL += "&charset=utf8mb4"
    else:
        DATABASE_URL += "?charset=utf8mb4"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()