# Square Updates - NyTex Fireworks

A comprehensive system for managing Square catalog updates, vendor data synchronization, and automated image management for NyTex Fireworks.

## 🚀 Quick Start

```bash
# Clone and setup
git clone [repository-url]
cd square_updates
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export SQUARE_ACCESS_TOKEN=your_token
export SQUARE_ENVIRONMENT=sandbox

# Run the application
cd app
python main.py
```

## 📁 Project Overview

This project consists of:

- **FastAPI Web Application** (`app/main.py`) - REST API for Square operations
- **Web Scrapers** - Automated image and data collection from vendor sites
- **Image Matching System** - AI-powered matching of vendor images to Square catalog
- **Square API Integration** - Full catalog management via Square API
- **Logging System** - Comprehensive logging with automatic rotation

## 🎯 Key Features

- ✅ **Multi-vendor support** - 6 major fireworks vendors
- ✅ **Automated image scraping** with rate limiting and duplicate prevention
- ✅ **Advanced image matching** using fuzzy algorithms and name normalization
- ✅ **Square API integration** for catalog management
- ✅ **Rotating logs** with automatic cleanup (no more 200MB+ log files!)
- ✅ **FastAPI web interface** for manual operations

## 🏗️ Architecture

```
square_updates/
├── app/                    # Main FastAPI application
│   ├── api/               # REST API endpoints
│   ├── services/          # Business logic
│   ├── scrapers/          # Vendor-specific scrapers
│   ├── data/images/       # Downloaded vendor images (5GB+)
│   └── logs/              # Rotating log files (cleaned up)
├── scripts/               # Maintenance utilities
└── venv/                  # Python virtual environment
```

## 📊 Current Status

### Recently Completed (December 2024):
- 🧹 **Major cleanup** - Removed 182.7MB of old log files and duplicate folders
- 🔧 **Fixed logging issues** - No more duplicate console messages
- 📝 **Implemented log rotation** - 10MB max files with 5 backups
- 🎯 **Enhanced image matching** - Better vendor name resolution
- 📈 **Improved documentation** - Updated and accurate README files

### Data Overview:
- **Vendor Images**: ~5GB across 6 vendor directories
- **Database**: SQLite with comprehensive product metadata
- **Logs**: Automatically rotating, maintained under 50MB total
- **Virtual Environment**: Clean, single venv directory

## 🔗 Documentation

- **[Detailed Documentation](app/README.md)** - Complete setup, usage, and API reference
- **[Log Cleanup Utility](scripts/cleanup_logs.py)** - Automated log maintenance
- **[Requirements](requirements.txt)** - Python dependencies

## 🛠️ Common Operations

```bash
# Web scraping
python scrape_fireworks.py

# Image matching and upload
python image_matcher.py

# Log cleanup
python scripts/cleanup_logs.py --live --keep-days 7

# FastAPI development server
cd app && python main.py
```

## 🎯 Vendor Support

| Vendor | Status | Type | Images |
|--------|--------|------|--------|
| Winco Fireworks | ✅ Active | WooCommerce | ~800MB |
| Red Rhino Fireworks | ✅ Active | WordPress | ~1.2GB |
| World Class Fireworks | ✅ Active | Shopify | ~900MB |
| Pyro Buy Fireworks | ✅ Active | Classic ASP | ~700MB |
| Raccoon Fireworks | ✅ Active | Custom | ~800MB |
| Supreme Fireworks | ✅ Active | Custom | ~600MB |

## 📈 Performance Improvements

- **Reduced storage**: Removed 182.7MB of redundant logs
- **Fixed memory leaks**: No more handler duplication in logging
- **Improved matching**: Better algorithms for vendor name resolution
- **Enhanced monitoring**: Detailed logs without console spam

## 🔧 Maintenance

The system now includes automated maintenance:
- **Log rotation**: Automatic file size management
- **Cleanup scripts**: Remove old temporary files
- **Health monitoring**: Track scraping and matching success rates

## 📞 Support

1. Check logs in `app/logs/` for detailed operation information
2. Use sandbox environment for testing
3. Review the [detailed documentation](app/README.md) for specific features
4. Monitor log rotation system for historical data

---

**Last Updated**: December 2024  
**Project Status**: ✅ Production Ready 