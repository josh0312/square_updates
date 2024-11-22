from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    site_name = Column(String(255), nullable=False)
    product_name = Column(String(255), nullable=False)
    sku = Column(String(100))
    price = Column(Float)
    description = Column(Text)
    category = Column(String(255))
    stock_status = Column(String(50))
    weight = Column(String(50))
    effects = Column(Text)
    image_url = Column(String(1024))
    local_image_path = Column(String(1024))
    product_url = Column(String(1024))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True) 