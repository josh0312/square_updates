class ImageDownloadConfig:
    def __init__(self, website, base_url, image_selector, name_attribute, output_directory):
        self.website = website
        self.base_url = base_url
        self.image_selector = image_selector
        self.name_attribute = name_attribute
        self.output_directory = output_directory

# Define the image download configurations
image_download_configs = [
    ImageDownloadConfig(
        website="Example Website 1",
        base_url="https://example1.com/",
        image_selector="img.product-image",
        name_attribute="data-product-id",
        output_directory="images/example1",
    ),
    ImageDownloadConfig(
        website="Example Website 2",
        base_url="https://example2.com/",
        image_selector="div.item-image > img",
        name_attribute="alt",
        output_directory="images/example2",
    ),
    # Add more configurations as needed
] 