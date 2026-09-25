"""Database models and session management"""
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings


# For development without PostgreSQL, use SQLite
if settings.DATABASE_URL.startswith("postgresql"):
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    except Exception:
        # Fallback to SQLite if PostgreSQL is not available
        db_url = "sqlite:///./landsync.db"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """System user for authentication and MFA"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    role = Column(String, default="Viewer")  # Admin, Official, Viewer

class Dataset(Base):
    """Uploaded dataset tracking"""
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    filename = Column(String, nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    source_type = Column(String, default="unknown")  # cadastral, drone_ori, satellite
    status = Column(String, default="uploaded")  # uploaded, processing, processed, failed
    record_count = Column(Integer, default=0)
    dataset_metadata = Column(JSON, nullable=True)



class Parcel(Base):
    """Reconciled parcel data"""
    __tablename__ = "parcels"

    parcel_id = Column(String, primary_key=True, index=True)
    dataset_id = Column(String, ForeignKey('datasets.id'), index=True)
    confidence = Column(Integer, nullable=False)
    priority = Column(String, nullable=False)  # HIGH, MEDIUM, LOW
    area_difference = Column(Float, default=0.0)
    geometry_conflict = Column(Boolean, default=False)
    attribute_conflict = Column(Boolean, default=False)
    duplicate_id = Column(Boolean, default=False)
    recommendation = Column(Text, nullable=False)
    official_label = Column(Integer, nullable=True)  # 0: No Conflict, 1: Conflict, NULL: Unlabeled
    labeled_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)

    # Geometry stored as GeoJSON

    cadastral_boundary = Column(JSON, nullable=False)
    drone_boundary = Column(JSON, nullable=True)

    # Additional metadata
    survey_number = Column(String, nullable=True)
    owner_name = Column(String, nullable=True)
    land_use = Column(String, nullable=True)
    area_cadastral_sqm = Column(Float, nullable=True)
    area_drone_sqm = Column(Float, nullable=True)
    village_name = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
