# Fireworks Product Scraper

A robust web scraping system designed to collect product information and images from various firework retailer websites. The scraper stores product metadata in a SQLite database and downloads high-resolution product images locally.

## Features

- 🔄 Multi-site support with configurable scraping rules
- 📦 Product metadata extraction (names, SKUs, prices, descriptions, etc.)
- 🖼️ High-resolution image downloading with duplicate prevention
- 📊 SQLite database integration for product data storage
- 🚦 Rate limiting and polite scraping practices
- 📝 Comprehensive logging system
- ⚙️ YAML-based website configuration
- 🔍 Support for various website structures (WooCommerce, Shopify, etc.)

## Prerequisites

- Python 3.7+
- pip (Python package installer)

## Installation

1. Clone the repository:
   git clone [your-repository-url]
   cd [repository-name]

2. Install required dependencies:
   pip install -r requirements.txt

3. Configure your database path in `scrape_fireworks.py`:
   engine = create_engine('sqlite:///fireworks.db')

## Configuration

The project uses `websites.yaml` for website configurations. Each website entry includes:

    name: Website Name
    url: https://website-url.com
    scraper: scraper_file.py
    enabled: true
    limit: 5  # Number of images to download (-1 for unlimited)
    note: "Website-specific notes and structure information"

## Usage

Run the scraper:
    python scrape_fireworks.py

The scraper will:
1. Load configurations from `websites.yaml`
2. Process each enabled website
3. Download images to site-specific folders
4. Store product metadata in the database
5. Generate detailed logs in `scraper.log`

## Project Structure

    ├── models/
    │   └── product.py
    ├── scrapers/
    │   ├── __init__.py
    │   ├── winco_scraper.py
    │   ├── redrhino_scraper.py
    │   ├── worldclass_scraper.py
    │   ├── pyrobuy_scraper.py
    │   └── raccoon_scraper.py
    ├── scrape_fireworks.py
    ├── websites.yaml
    ├── requirements.txt
    ├── scraper.log
    └── README.md

## Supported Websites

Currently supports:
- Winco Fireworks Texas
- Red Rhino Fireworks
- World Class Fireworks
- Pyro Buy Fireworks
- Raccoon Fireworks

## Image Storage

Images are stored in the following structure:

    /Users/joshgoble/Downloads/firework_pics/
    └── [domain-name]/
        └── [product-images].jpg

## Database Schema

Products are stored with the following information:
- Site name
- Product name
- SKU
- Price
- Description
- Category
- Stock status
- Effects
- Product URL
- Image URL
- Local image path
- Timestamps

## Error Handling

The scraper includes:
- Comprehensive error logging
- Network error recovery
- File system error handling
- Database transaction management

## Adding New Websites

To add a new website to the scraper:

1. Create a new scraper file in the `scrapers` directory (e.g., `new_website_scraper.py`).
2. Implement the website-specific scraping logic in the new scraper file, following the existing scraper structure.
3. Update the `websites.yaml` file with the new website's configuration, including the scraper file name.
4. Run the `scrape_fireworks.py` script to start scraping the new website.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

[Your chosen license]

## Acknowledgments

- BeautifulSoup4 for HTML parsing
- SQLAlchemy for database operations
- Requests for HTTP operations
- PyYAML for configuration management

## Notes

- Ensure you have proper permissions to scrape target websites
- Adjust rate limiting as needed to be respectful to servers
- Monitor scraper.log for detailed operation information
