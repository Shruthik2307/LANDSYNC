from database import SessionLocal, User
from sqlalchemy import Column, String
import uuid

db = SessionLocal()
email = "test@landsync.com"
user = User(
    id=uuid.uuid4(),
    email=email,
    password_hash="password123",
    role="Admin"
)
db.add(user)
db.commit()
print(f"User {email} created.")
