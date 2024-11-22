from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.product import Product, Base

def check_products():
    # Create engine and session
    engine = create_engine('sqlite:///fireworks.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all Winco products
        products = session.query(Product).filter_by(site_name='Winco Fireworks Texas').all()
        
        print(f"\nFound {len(products)} Winco products:")
        print("-" * 80)
        
        for product in products:
            print(f"\nProduct: {product.product_name}")
            print(f"SKU: {product.sku}")
            print(f"Price: ${product.price if product.price else 'Not set'}")
            print(f"Category: {product.category if product.category else 'Not set'}")
            print(f"Stock Status: {product.stock_status if product.stock_status else 'Not set'}")
            print(f"Effects: {product.effects if product.effects else 'None'}")
            print(f"Image Path: {product.local_image_path}")
            print(f"Last Updated: {product.updated_at}")
            print("-" * 80)
            
    finally:
        session.close()

if __name__ == "__main__":
    check_products() 