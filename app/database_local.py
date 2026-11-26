"""
로컬 개발 환경용 데이터베이스 설정 (SQLite 사용)
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 로컬 SQLite 데이터베이스
DB_FILE = "babba_local.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE}"

# SQLite 엔진 생성 (연결 풀 없음)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # SQL 쿼리 로깅 비활성화
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
