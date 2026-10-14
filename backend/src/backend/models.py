from sqlalchemy import Column, Integer, String, DateTime
from .database import Base
import datetime

class RoomSimulation(Base):
    __tablename__ = "room_simulations"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=True)
    external_link = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
