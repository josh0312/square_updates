from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.product import Product, Base
from app.utils.logger import setup_logger

logger = setup_logger('test_db_items')

def test_db_products():
    """Test database products retrieval and structure"""
    # Create engine and session
    engine = create_engine('sqlite:///fireworks.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all Winco products
        products = session.query(Product).filter_by(site_name='Winco Fireworks Texas').all()
        
        logger.info(f"\nFound {len(products)} Winco products:")
        logger.info("-" * 80)
        
        for product in products:
            logger.info(f"\nProduct: {product.product_name}")
            logger.info(f"SKU: {product.sku}")
            logger.info(f"Price: ${product.price if product.price else 'Not set'}")
            logger.info(f"Category: {product.category if product.category else 'Not set'}")
            logger.info(f"Stock Status: {product.stock_status if product.stock_status else 'Not set'}")
            logger.info(f"Effects: {product.effects if product.effects else 'None'}")
            logger.info(f"Image Path: {product.local_image_path}")
            logger.info(f"Last Updated: {product.updated_at}")
            logger.info("-" * 80)
            
    finally:
        session.close()

if __name__ == "__main__":
    test_db_products() 