from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class BaseProduct(Base):
    """Base product information that's common across all sources"""
    __tablename__ = 'base_products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor_products = relationship("VendorProduct", back_populates="base_product")
    square_product = relationship("SquareProduct", back_populates="base_product", uselist=False)
    nytex_product = relationship("NytexProduct", back_populates="base_product", uselist=False)

class VendorProduct(Base):
    """Product information from vendor websites"""
    __tablename__ = 'vendor_products'
    
    id = Column(Integer, primary_key=True)
    base_product_id = Column(Integer, ForeignKey('base_products.id'))
    vendor_name = Column(String(255), nullable=False)  # e.g., "Winco", "Red Rhino"
    vendor_sku = Column(String(100))
    vendor_price = Column(Float)
    vendor_description = Column(Text)
    vendor_category = Column(String(255))
    vendor_image_url = Column(String(1024))
    local_image_path = Column(String(1024))
    vendor_product_url = Column(String(1024))
    vendor_video_url = Column(String(1024))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    base_product = relationship("BaseProduct", back_populates="vendor_products")

class SquareProduct(Base):
    """Product information from Square"""
    __tablename__ = 'square_products'
    
    id = Column(Integer, primary_key=True)
    base_product_id = Column(Integer, ForeignKey('base_products.id'))
    square_id = Column(String(255), unique=True)
    square_version = Column(Integer)
    name = Column(String(255))
    description = Column(Text)
    category_id = Column(String(255))
    price_money = Column(Integer)  # Store in cents
    image_ids = Column(Text)  # Store as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    base_product = relationship("BaseProduct", back_populates="square_product")

class NytexProduct(Base):
    """Product information from shop.nytexfireworks.com"""
    __tablename__ = 'nytex_products'
    
    id = Column(Integer, primary_key=True)
    base_product_id = Column(Integer, ForeignKey('base_products.id'))
    product_url = Column(String(1024))
    description = Column(Text)
    price = Column(Float)
    has_video = Column(Boolean, default=False)
    video_url = Column(String(1024))
    video_type = Column(String(50))  # e.g., "youtube", "vimeo", "hosted"
    image_url = Column(String(1024))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    base_product = relationship("BaseProduct", back_populates="nytex_product") 