import httpx
import logging
import os

from dotenv import load_dotenv
load_dotenv()

PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")  # Replace with your actual API key
PIPEDRIVE_API_BASE_URL = "https://api.pipedrive.com/v1"

async def update_pipedrive_deal(deal_id: str, payload: dict):
    url = f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}"
    headers = {
        "x-api-token": PIPEDRIVE_API_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            logging.info(f"Updated Pipedrive deal {deal_id} successfully.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to update deal {deal_id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error during Pipedrive update: {e}")
            
            
def map_nethunt_fields_to_pipedrive(record_fields: dict) -> dict:
    key_mapping = {
        "title": "Name",
        "Email": "Email Primary",
        "Phone": "Phone",
        "Stage": "Stage",
        "Pipeline": "Pipeline",
        "b4657a3853fbae1a21222a1f6265dffd1111fc55": "First Name", 
        "fb3c253d2c30416d52191beb3c443f96133c571c": "West Chester Availablity",
        "4f01b3626ca1c664c9dec11aad381c405e73bc5d": "Philadelphia Availability",
        "4d7a7e1d75b47934b2734ca8d4e270b5e80dd40f": "Main Line Availability",
        "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "Address",
        "fe16f95ae1442816f87a9c4ee18b5056f8743030": "Preferred Days / Availability",
        "e042a0ac93f8d43206b3a96cbe21f24610b74276": "Chef Assigned",
        "d64ea5791d2efd1b160cba0b4dde0d997d1b513d": "Home Assistant Assigned",
        "73950ad98eab1e4948d742be2fa34897e457a2f4": "Past Providers",
        "ac2082c8795591a9fb4c4ee0ee6062a11daea132": "Service Interest",
        "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Last Name",
        "label": "Contact Status",
        # Additional mappings for lost reason fields
        "lost_reason": "Lost Reason",  # For team data
        "client_lost_reasons": "Client Lost Reasons"  # For person data
    }

    payload = {}
    for pipedrive_key, field_name in key_mapping.items():
        # Normalize field name for lost reason
        if field_name == "Lost Reason":
            # NetHunt may send as 'Lost Reason' or 'lost_reason'
            value = record_fields.get("Lost Reason") or record_fields.get("lost_reason")
            if value:
                payload["lost_reason"] = value
            continue
        if field_name == "Client Lost Reasons":
            value = record_fields.get("Client Lost Reasons") or record_fields.get("client_lost_reasons")
            if value:
                payload["client_lost_reasons"] = value
            continue
        # Standard mapping
        if field_name in record_fields:
            value = record_fields[field_name]
            if isinstance(value, list):
                value = value[0] if value else None
            payload[pipedrive_key] = value
    print(f"Mapped fields for Pipedrive update: {payload}")
    
    return payload