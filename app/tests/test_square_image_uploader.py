import os
from square.client import Client
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    filename='square_image_upload.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

class SquareImageUploader:
    def __init__(self):
        self.client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment=os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
        )
        self.catalog_api = self.client.catalog
        
    def upload_image(self, image_path, item_id):
        """Upload a single image and attach it to a catalog item."""
        try:
            # Read the image file
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            
            # Create the image in Square
            result = self.catalog_api.create_catalog_image(
                body={
                    "idempotency_key": f"image_{item_id}_{os.path.basename(image_path)}",
                    "image": {
                        "name": os.path.basename(image_path),
                        "type": "IMAGE",
                    },
                    "image_file": image_data
                }
            )
            
            if result.is_success():
                image_id = result.body['catalog_object']['id']
                logging.info(f"Successfully uploaded image: {image_id}")
                
                # Associate the image with the catalog item
                self._associate_image_with_item(image_id, item_id)
                return image_id
            else:
                logging.error(f"Failed to upload image: {result.errors}")
                return None
                
        except Exception as e:
            logging.error(f"Error uploading image: {str(e)}")
            return None
            
    def _associate_image_with_item(self, image_id, item_id):
        """Associate an uploaded image with a catalog item."""
        try:
            result = self.catalog_api.update_catalog_image(
                body={
                    "idempotency_key": f"associate_{image_id}_{item_id}",
                    "image": {
                        "id": image_id,
                        "item_ids": [item_id]
                    }
                }
            )
            
            if result.is_success():
                logging.info(f"Successfully associated image {image_id} with item {item_id}")
            else:
                logging.error(f"Failed to associate image: {result.errors}")
                
        except Exception as e:
            logging.error(f"Error associating image: {str(e)}")

def test_image_upload():
    """Test function to upload an image for a single catalog item."""
    uploader = SquareImageUploader()
    
    # Test parameters - replace with actual values
    test_image_path = "path/to/test/image.jpg"
    test_item_id = "YOUR_TEST_ITEM_ID"
    
    logging.info(f"Starting test upload for item {test_item_id}")
    
    # Attempt to upload and associate the image
    image_id = uploader.upload_image(test_image_path, test_item_id)
    
    if image_id:
        logging.info("Test completed successfully")
    else:
        logging.error("Test failed")

if __name__ == "__main__":
    test_image_upload() 