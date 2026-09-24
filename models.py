from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    ruc = Column(String, nullable=True)
    giro = Column(String, nullable=True)
    credits = Column(Integer, default=5) # 5 créditos gratis al registrarse
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    inventories = relationship("InventoryJob", back_populates="owner")

class InventoryJob(Base):
    __tablename__ = "inventories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    video_url = Column(String)
    status = Column(String, default="processing") # processing, completed, error
    result_json = Column(Text, nullable=True)
    deducted_credits = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User", back_populates="inventories")
