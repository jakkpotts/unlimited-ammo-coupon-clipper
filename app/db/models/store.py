from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
from app.db.models.user import user_stores

class Store(Base):
    """Store model for managing store information"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    base_url = Column(String, unique=True, index=True)
    login_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", secondary=user_stores, back_populates="stores")

    def __repr__(self):
        return f"<Store {self.name}>"

    # We don't store credentials, they are provided at runtime 