key_mapping = {
    "b4657a3853fbae1a21222a1f6265dffd1111fc55": "First Name",
    "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Last name",
    "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "Address",
    "fb3c253d2c30416d52191beb3c443f96133c571c": "West Chester Availability",
    "4f01b3626ca1c664c9dec11aad381c405e73bc5d": "Philadelphia Availability",
    "4d7a7e1d75b47934b2734ca8d4e270b5e80dd40f": "Main Line Availability",
    "fe16f95ae1442816f87a9c4ee18b5056f8743030": "Preferred Days or Availability",
    "e042a0ac93f8d43206b3a96cbe21f24610b74276": "Chef Assigned",
    "d64ea5791d2efd1b160cba0b4dde0d997d1b513d": "Home Assistant Assigned",
    "73950ad98eab1e4948d742be2fa34897e457a2f4": "Past Providers",
    "3d5c1f11c39686c2d445c279f00ee873c3aa5847": "Services Recieved",
    "ac2082c8795591a9fb4c4ee0ee6062a11daea132": "Service Interest",
}

def extract_fields(deal_data, key_mapping):
    extracted_fields = {}
    for key, field_name in key_mapping.items():
        extracted_fields[field_name] = deal_data.get(key, "")
    return extracted_fields

def update_nethunt_record(deal_data, api_key):
    fields_to_update = extract_fields(deal_data, key_mapping)
    update_payload = {
        "fieldActions": {field: {"overwrite": True, "add": value} for field, value in fields_to_update.items()}
    }
    # Example API call (replace with actual implementation)
    print(f"Updating NetHunt record with fields: {update_payload} and API key: {api_key}")

# Example usage
deal_data = {
    # ...existing deal data...
    "b4657a3853fbae1a21222a1f6265dffd1111fc55": "Testing",
    "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Singh Sahab",
    "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "test4@gmail.com",
    "fe16f95ae1442816f87a9c4ee18b5056f8743030": "2",
    "e042a0ac93f8d43206b3a96cbe21f24610b74276": "Some",
    # ...other fields...
}
api_key = "YWdpbGVtb3JwaHNvbHV0aW9uc0BnbWFpbC5jb206MzA3NDFmMGEtZDYyZC00NzAzLWIwZDQtMGEwM2ZlNmY4Nzgy"
update_nethunt_record(deal_data, api_key)
