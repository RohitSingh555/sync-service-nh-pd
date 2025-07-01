import httpx
import logging
import os

from dotenv import load_dotenv
from src.stage_mapping import get_stage_id, get_pipeline_id

load_dotenv()

PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")  # Replace with your actual API key
PIPEDRIVE_API_BASE_URL = "https://api.pipedrive.com/v1"

# Map pipeline name to its first stage name
PIPELINE_FIRST_STAGE = {
    "Sales": "Form Submitted",
    "HA Candidates": "Application Submitted",
    "Staff": "Onboard**",
    "Clients": "Signed & Paid",
    "CHEF Candidates": "Application Submitted",
}

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
    logging.info(f"map_nethunt_fields_to_pipedrive called with: ")
    payload = {}  # Ensure payload is defined before any use
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

    # Correct reverse mapping for Service Interest and Services Received Updated
    service_interest_reverse_map = {
        "Chef Services": 63,
        "Home Assistant Services": 64,
        "Combo Services": 66
    }
    services_recieved_reverse_map = {
        "Chef Service": 226,
        "Home Assistant Service": 227,
        "Combo Service": 228,
        "Organization Service": 229
    }

    # Services Received Updated from checkboxes
    services_checkbox_reverse_map = {
        "Chef Service": 226,
        "Home Assistant Services": 227,
        "Combo Services": 228
    }
    services_ids = []
    for nh_field, pid in services_checkbox_reverse_map.items():
        val = record_fields.get(nh_field)
        if val is True or val == "True" or val == 1:
            services_ids.append(pid)
    if services_ids:
        payload["3d5c1f11c39686c2d445c279f00ee873c3aa5847"] = services_ids if len(services_ids) > 1 else services_ids[0]

    logging.info(f"map_nethunt_fields_to_pipedrive called with: {record_fields}")
    pipeline_set = False
    for pipedrive_key, field_name in key_mapping.items():
        # Pipeline mapping (convert pipeline name to pipeline ID)
        if field_name == "Pipeline":
            pipeline_name = record_fields.get("Pipeline")
            if pipeline_name:
                pipeline_id = get_pipeline_id(pipeline_name)
                if pipeline_id:
                    payload["pipeline_id"] = pipeline_id
                    logging.info(f"Mapped pipeline '{pipeline_name}' to ID {pipeline_id}")
                    # Always set stage_id to the first stage of the new pipeline
                    first_stage_name = PIPELINE_FIRST_STAGE.get(pipeline_name)
                    if first_stage_name:
                        stage_id = get_stage_id(first_stage_name)
                        if stage_id:
                            payload["stage_id"] = stage_id
                            logging.info(f"Set stage_id to first stage '{first_stage_name}' (ID {stage_id}) for pipeline '{pipeline_name}' (pipeline change)")
                        else:
                            logging.warning(f"Could not find stage ID for first stage '{first_stage_name}' of pipeline '{pipeline_name}'")
                    else:
                        logging.warning(f"No first stage mapping found for pipeline '{pipeline_name}'")
                    pipeline_set = True
                else:
                    logging.warning(f"Could not find pipeline ID for pipeline name: '{pipeline_name}'")
            continue
        # Stage mapping (convert stage name to stage ID)
        if field_name == "Stage":
            # Only set stage_id from Stage if pipeline is not being changed in this update
            if not pipeline_set:
                stage_name = record_fields.get("Stage")
                if stage_name:
                    stage_id = get_stage_id(stage_name)
                    if stage_id:
                        payload["stage_id"] = stage_id
                        logging.info(f"Mapped stage '{stage_name}' to ID {stage_id}")
                    else:
                        logging.warning(f"Could not find stage ID for stage name: '{stage_name}'")
            else:
                logging.info("Pipeline is being changed, so stage_id is set to the first stage of the new pipeline, not from the Stage field.")
            continue
        # Reverse mapping for Service Interest (handle both 'Service Interest' and 'Current Services')
        if field_name == "Service Interest":
            service_interest = record_fields.get("Service Interest") or record_fields.get("Current Services")
            if not service_interest:
                service_interest = record_fields.get("Current Services")
                if service_interest:
                    logging.info("Using 'Current Services' as Service Interest for mapping.")
            else:
                logging.info("Using 'Service Interest' for mapping.")
            if service_interest:
                if isinstance(service_interest, str):
                    service_interest = [service_interest]
                logging.info(f"Service Interest raw values: {service_interest}")
                ids = [service_interest_reverse_map.get(s) for s in service_interest if s in service_interest_reverse_map]
                logging.info(f"Service Interest mapped IDs: {ids}")
                if ids:
                    payload[pipedrive_key] = ids if len(ids) > 1 else ids[0]
            continue
        # Reverse mapping for Current Services (Services Received Updated)
        if field_name == "Current Services":
            current_services = record_fields.get("Current Services")
            if current_services:
                if isinstance(current_services, str):
                    current_services = [current_services]
                logging.info(f"Current Services raw values: {current_services}")
                ids = [services_recieved_reverse_map.get(s) for s in current_services if s in services_recieved_reverse_map]
                logging.info(f"Current Services mapped IDs: {ids}")
                if ids:
                    payload["3d5c1f11c39686c2d445c279f00ee873c3aa5847"] = ids if len(ids) > 1 else ids[0]
            continue
        # Normalize field name for lost reason
        if field_name == "Lost Reason":
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
    # Handle Service Interest and Current Services if not in key_mapping (for safety)
    if "Service Interest" in record_fields or "Current Services" in record_fields:
        service_interest = record_fields.get("Service Interest") or record_fields.get("Current Services")
        if service_interest:
            if isinstance(service_interest, str):
                service_interest = [service_interest]
            logging.info(f"[Safety] Service Interest raw values: {service_interest}")
            ids = [service_interest_reverse_map.get(s) for s in service_interest if s in service_interest_reverse_map]
            logging.info(f"[Safety] Service Interest mapped IDs: {ids}")
            if ids:
                payload["ac2082c8795591a9fb4c4ee0ee6062a11daea132"] = ids if len(ids) > 1 else ids[0]
    if "Current Services" in record_fields:
        current_services = record_fields.get("Current Services")
        if current_services:
            if isinstance(current_services, str):
                current_services = [current_services]
            logging.info(f"[Safety] Current Services raw values: {current_services}")
            ids = [services_recieved_reverse_map.get(s) for s in current_services if s in services_recieved_reverse_map]
            logging.info(f"[Safety] Current Services mapped IDs: {ids}")
            if ids:
                payload["3d5c1f11c39686c2d445c279f00ee873c3aa5847"] = ids if len(ids) > 1 else ids[0]
    logging.info(f"Mapped fields for Pipedrive update: {payload}")
    return payload