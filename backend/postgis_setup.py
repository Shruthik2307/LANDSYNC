"""
PostGIS Database Setup & Configuration
Spatial database schema for production deployment
"""
from sqlalchemy import create_engine, Column, String, Float, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape, from_shape
import logging
from typing import Optional
from config import DATABASE_URL

logger = logging.getLogger(__name__)

Base = declarative_base()


class ParcelRecord(Base):
    """PostGIS parcel table with spatial indexing"""
    __tablename__ = 'parcels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    parcel_id = Column(String(255), unique=True, nullable=False, index=True)

    # Spatial columns with SRID 3857 (Web Mercator)
    cadastral_geom = Column(Geometry('POLYGON', srid=3857), nullable=False)
    municipal_geom = Column(Geometry('POLYGON', srid=3857))
    drone_geom = Column(Geometry('POLYGON', srid=3857))

    # Reconciliation scores
    confidence = Column(Float, nullable=False)
    priority = Column(String(10), nullable=False)
    area_difference = Column(Float, default=0.0)

    # Conflict flags
    geometry_conflict = Column(Boolean, default=False, index=True)
    attribute_conflict = Column(Boolean, default=False)
    duplicate_id = Column(Boolean, default=False)
    topology_valid = Column(Boolean, default=True)

    # Recommendations
    recommendation = Column(Text)

    # Source tracking
    cadastral_source = Column(String(255))
    municipal_source = Column(String(255))
    drone_source = Column(String(255))
    last_updated = Column(String(50))


class ConflictRecord(Base):
    """Conflict tracking table"""
    __tablename__ = 'conflicts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    parcel_id = Column(String(255), nullable=False, index=True)
    conflict_type = Column(String(50), nullable=False)
    severity = Column(String(20))
    description = Column(Text)
    resolution_status = Column(String(50), default='pending')
    created_at = Column(String(50))


class PostGISDatabase:
    """PostGIS database manager"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = None
        self.Session = None

    def connect(self):
        """Connect to PostgreSQL+PostGIS database"""
        try:
            self.engine = create_engine(self.database_url)
            self.Session = sessionmaker(bind=self.engine)

            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute("SELECT PostGIS_Version();")
                version = result.fetchone()[0]
                logger.info(f"Connected to PostGIS: {version}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to PostGIS: {e}")
            return False

    def create_schema(self):
        """Create tables and spatial indexes"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database schema created")

            # Create spatial indexes
            with self.engine.connect() as conn:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_parcels_cadastral_geom
                    ON parcels USING GIST (cadastral_geom);
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_parcels_municipal_geom
                    ON parcels USING GIST (municipal_geom);
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_parcels_drone_geom
                    ON parcels USING GIST (drone_geom);
                """)
                conn.commit()
                logger.info("Spatial indexes created")

        except Exception as e:
            logger.error(f"Failed to create schema: {e}")

    def insert_parcel(self, parcel_data: dict):
        """Insert parcel with spatial geometries"""
        session = self.Session()
        try:
            # Convert Shapely geometries to PostGIS format
            from shapely.geometry import shape

            cadastral_geom = from_shape(
                parcel_data['boundaries']['cadastral'],
                srid=3857
            )

            parcel = ParcelRecord(
                parcel_id=parcel_data['parcel_id'],
                cadastral_geom=cadastral_geom,
                confidence=parcel_data['confidence'],
                priority=parcel_data['priority'],
                area_difference=parcel_data['area_difference'],
                geometry_conflict=parcel_data['geometry_conflict'],
                attribute_conflict=parcel_data['attribute_conflict'],
                duplicate_id=parcel_data['duplicate_id'],
                recommendation=parcel_data['recommendation']
            )

            session.add(parcel)
            session.commit()
            logger.info(f"Inserted parcel {parcel_data['parcel_id']}")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert parcel: {e}")
        finally:
            session.close()

    def spatial_query(self, bbox: tuple):
        """
        Query parcels within bounding box

        Args:
            bbox: (minx, miny, maxx, maxy)

        Returns:
            List of parcel records
        """
        session = self.Session()
        try:
            from geoalchemy2.functions import ST_MakeEnvelope, ST_Intersects

            envelope = ST_MakeEnvelope(*bbox, 3857)
            results = session.query(ParcelRecord).filter(
                ST_Intersects(ParcelRecord.cadastral_geom, envelope)
            ).all()

            return results

        except Exception as e:
            logger.error(f"Spatial query failed: {e}")
            return []
        finally:
            session.close()


# Global database instance
postgis_db = PostGISDatabase()
