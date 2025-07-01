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
    "3d5c1f11c39686c2d445c279f00ee873c3aa5847": "Services Received Updated",
    "ac2082c8795591a9fb4c4ee0ee6062a11daea132": "Service Interest",
}

service_interest_map = {
    63: "Chef Services",
    64: "Home Assistant Services",
    66: "Combo Services"
}
services_recieved_map = {
    226: "Chef Service",
    227: "Home Assistant Service",
    228: "Combo Service",
    229: "Organization Service"
}
service_interest_reverse_map = {v: k for k, v in service_interest_map.items()}
services_recieved_reverse_map = {v: k for k, v in services_recieved_map.items()}

def extract_fields(deal_data, key_mapping):
    extracted_fields = {}
    for key, field_name in key_mapping.items():
        if field_name == "Service Interest":
            raw_val = deal_data.get(key, "")
            if isinstance(raw_val, int):
                extracted_fields[field_name] = service_interest_map.get(raw_val, str(raw_val))
            elif isinstance(raw_val, str) and raw_val.isdigit():
                extracted_fields[field_name] = service_interest_map.get(int(raw_val), raw_val)
            else:
                extracted_fields[field_name] = raw_val
        elif field_name == "Services Received Updated":
            raw_val = deal_data.get(key, "")
            if isinstance(raw_val, int):
                extracted_fields[field_name] = services_recieved_map.get(raw_val, str(raw_val))
            elif isinstance(raw_val, str) and raw_val.isdigit():
                extracted_fields[field_name] = services_recieved_map.get(int(raw_val), raw_val)
            else:
                extracted_fields[field_name] = raw_val
        else:
            extracted_fields[field_name] = deal_data.get(key, "")
    return extracted_fields

def update_nethunt_record(deal_data, api_key):
    fields_to_update = extract_fields(deal_data, key_mapping)
    # Reverse mapping for update to Pipedrive
    payload = {}
    si = fields_to_update.get("Service Interest")
    if si:
        if isinstance(si, str):
            si = [si]
        ids = [service_interest_reverse_map.get(s) for s in si if s in service_interest_reverse_map]
        if ids:
            payload["ac2082c8795591a9fb4c4ee0ee6062a11daea132"] = ids if len(ids) > 1 else ids[0]
    sr = fields_to_update.get("Services Received Updated")
    if sr:
        if isinstance(sr, str):
            sr = [sr]
        ids = [services_recieved_reverse_map.get(s) for s in sr if s in services_recieved_reverse_map]
        if ids:
            payload["3d5c1f11c39686c2d445c279f00ee873c3aa5847"] = ids if len(ids) > 1 else ids[0]
    # Add other fields as needed
    print(f"Updating NetHunt record with fields: {payload} and API key: {api_key}")

