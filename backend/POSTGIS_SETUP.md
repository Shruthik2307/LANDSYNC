"""
Alembic migration script initialization
Run: alembic init alembic
Then: alembic revision --autogenerate -m "Initial schema"
Finally: alembic upgrade head
"""

# Migration commands documented for production setup:
# 
# 1. Install PostgreSQL + PostGIS:
#    sudo apt install postgresql postgresql-contrib postgis
#
# 2. Create database:
#    sudo -u postgres psql
#    CREATE DATABASE landsync;
#    CREATE USER landsync WITH PASSWORD 'landsync';
#    GRANT ALL PRIVILEGES ON DATABASE landsync TO landsync;
#    \c landsync
#    CREATE EXTENSION postgis;
#
# 3. Update .env with connection string:
#    DATABASE_URL=postgresql://landsync:landsync@localhost:5432/landsync
#
# 4. Run migrations:
#    cd backend
#    alembic init alembic
#    alembic revision --autogenerate -m "Initial PostGIS schema"
#    alembic upgrade head
