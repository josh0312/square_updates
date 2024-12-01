"""Mock responses for Square API tests"""

VENDOR_RESPONSE = {
    "vendors": [
        {"id": "RR", "name": "Red Rhino"},
        {"id": "WN", "name": "Winco"},
        {"id": "SP", "name": "Supreme"},
        {"id": "WC", "name": "Jakes"},
        {"id": "RN", "name": "Raccoon"},
        {"id": "AWF", "name": "AWF"},
        {"id": "CHW", "name": "CHW"},
        {"id": "GAR", "name": "Garrets"},
        {"id": "NT", "name": "NyTex"},
        {"id": "PB", "name": "Pyro Buy"}
    ]
}

CATALOG_ITEMS_RESPONSE = {
    "objects": [
        {
            "id": "item1",
            "type": "ITEM",
            "item_data": {
                "name": "Artillery Shells - Crackling",
                "image_ids": [],  # No primary image
                "variations": [
                    {
                        "id": "var1",
                        "item_variation_data": {
                            "name": "RR",
                            "sku": "RR123",
                            "image_ids": [],  # No variation image
                            "item_variation_vendor_infos": [
                                {
                                    "item_variation_vendor_info_data": {
                                        "vendor_id": "RR"
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "id": "var2",
                        "item_variation_data": {
                            "name": "SP",
                            "sku": "SP123",
                            "image_ids": [],  # No variation image
                            "item_variation_vendor_infos": [
                                {
                                    "item_variation_vendor_info_data": {
                                        "vendor_id": "SP"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    ]
} 