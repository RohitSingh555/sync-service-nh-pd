# src/sync_engine.py
import requests
import base64
import httpx
import logging
from src.clients.nethunt import nethunt_client
import json
import os
import httpx
import logging
from dotenv import load_dotenv
load_dotenv()

NETHUNT_API_KEY = os.getenv("NETHUNT_API_KEY")
NETHUNT_EMAIL = os.getenv("NETHUNT_EMAIL")
PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"

BASE_URL = "https://nethunt.com/api/v1/zapier/actions/update-record"

def get_auth_header(email: str, api_key: str):
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

async def get_pipedrive_activity_by_subject(title: str, api_token: str, activity_type: str = None) -> dict | None:
    url = "https://api.pipedrive.com/api/v2/activities"
    params = {
        "limit": 10,
        "sort_by": "add_time",
        "sort_direction": "desc",
        "api_token": api_token
    }

    if activity_type:
        params["type"] = activity_type

    logging.debug(f"Searching for Pipedrive activity with title: '{title}' and type: '{activity_type}'")

    async with httpx.AsyncClient() as client:
        try:
            logging.debug(f"Sending GET request to {url} with params: {params}")
            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            activities = data.get("data", [])

            logging.debug(f"Fetched {len(activities)} recent activities from Pipedrive")

            for activity in activities:
                subject = activity.get("subject", "")
                logging.debug(f"Checking activity subject: '{subject}'")
                if subject == title:
                    logging.info(f"Found matching Pipedrive activity with title '{title}'")
                    return activity

            logging.info(f"No activity found with title '{title}' in Pipedrive")
            return None

        except Exception as e:
            logging.warning(f"Failed to fetch activities from Pipedrive: {e}")
            return None


async def does_activity_exist(title: str, api_token: str, activity_type: str = None) -> bool:
    url = "https://api.pipedrive.com/api/v2/activities"
    params = {
        "limit": 10,
        "sort_by": "add_time",
        "sort_direction": "desc",
        "api_token": api_token
    }

    if activity_type:
        params["type"] = activity_type

    logging.debug(f"Checking existence of activity with title: '{title}' and type: '{activity_type}'")

    async with httpx.AsyncClient() as client:
        try:
            logging.debug(f"Sending GET request to {url} with params: {params}")
            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            activities = data.get("data", [])

            logging.debug(f"Fetched {len(activities)} recent activities from Pipedrive")

            for activity in activities:
                subject = activity.get("subject", "")
                logging.debug(f"Checking activity subject: '{subject}'")
                if subject == title:
                    logging.info(f"Activity with title '{title}' already exists in Pipedrive")
                    return True

            logging.info(f"No activity found with title '{title}' in Pipedrive")
            return False

        except Exception as e:
            logging.warning(f"Failed to fetch activities from Pipedrive: {e}")
            return False


async def update_nethunt_record(record_id: str, fields: dict):
    url = f"{BASE_URL}/{record_id}"
    headers = {
        "Content-Type": "application/json",
        **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
    }

    payload = {
        "fieldActions": fields
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            logging.info(f"Successfully updated NetHunt record {record_id}")
            return response.json()
        else:
            logging.error(f"Failed to update NetHunt record {record_id}: {response.status_code} - {response.text}")
            return None


async def fetch_deal_ids_from_record_links(record_links: list[str]) -> list[str]:
    deal_ids = []
    async with httpx.AsyncClient() as client:
        for record_id in record_links:
            headers = {
                "Content-Type": "application/json",
                **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
            }
            try:
                url = "https://nethunt.com/api/v1/zapier/searches/find-record/67e17578cc9bea52af34a26f"
                params = {"recordId": record_id}
                print(f"[DEBUG] Fetching recordId: {record_id} from URL: {url}")
                print(f"[DEBUG] Headers: {headers}")
                print(f"[DEBUG] Params: {params}")

                response = await client.get(url, headers=headers, params=params)
                print(f"[DEBUG] Response status code: {response.status_code}")
                print(f"[DEBUG] Raw response text: {response.text}")

                response.raise_for_status()
                result = response.json()

                print(f"[DEBUG] Parsed response JSON:\n{json.dumps(result, indent=2)}")

                if result and isinstance(result, list):
                    record = result[0]
                    pipedrive_id = record.get("fields", {}).get("Pipedrive Record Id")
                    print(f"[DEBUG] Extracted Pipedrive Record Id: {pipedrive_id}")
                    if pipedrive_id:
                        deal_ids.append(pipedrive_id)
                else:
                    print(f"[DEBUG] No valid record found for record ID: {record_id}")

            except Exception as e:
                logging.warning(f"Failed to fetch Pipedrive Record ID for record {record_id}: {e}")
                print(f"[ERROR] Exception for record {record_id}: {e}")
    return deal_ids

# PIPEDRIVE_API
async def handle_deals_webhook(body: dict):
    current = body.get("data", {})
    previous = body.get("previous", {})
    activity_id = str(current.get("id"))

    # Detect only changed fields
    updated_fields = {
        key: current[key]
        for key in current.keys()
        if current.get(key) != previous.get(key)
    }

    if not updated_fields:
        logging.info(f"No changes detected for activity {activity_id}")
        return

    logging.info(f"Activity {activity_id} updated with fields: {updated_fields}")

    person_id = current.get("person_id")
    if not person_id:
        logging.warning(f"No person_id associated with activity {activity_id}")
        return

    headers = {
        "Accept": "application/json",
        "x-api-token": PIPEDRIVE_API_TOKEN
    }

    async with httpx.AsyncClient() as client:
        # Fetch person
        person_url = f"{PIPEDRIVE_BASE_URL}/persons/{person_id}"
        person_response = await client.get(person_url, headers=headers)

        if person_response.status_code != 200:
            logging.error(f"Failed to fetch person {person_id}: {person_response.status_code} - {person_response.text}")
            return

        person_data = person_response.json()
        logging.info(f"Person data for ID {person_id}: {person_data}")


        # ------------------------
        # Deal fetch and folder/record ID extraction
        # ------------------------
        deal_id = current.get("id")
        nethunt_folder_id = None
        nethunt_record_id = None
        nethunt_team_record_id = None

        if deal_id:
            deal_url = f"{PIPEDRIVE_BASE_URL}/deals/{deal_id}"
            deal_response = await client.get(deal_url, headers=headers)

            if deal_response.status_code != 200:
                logging.error(f"Failed to fetch deal {deal_id}: {deal_response.status_code} - {deal_response.text}")
                return

            deal_data = deal_response.json()
            logging.info(f"Deal data for ID {deal_id}: {deal_data}")

            # Nethunt Hardcoded field keys
            record_id_key = "55eb66f5d38ea77a03e23d3f0f3dd31b891739d1"
            team_record_id_key = "b0d55c75b49af56fd540cd2e53af1de5cba0b340"
            folder_id_key = "6cff18ff6ad02610ded066fab268f76d7d6431c9"

            deal_fields = deal_data.get("data", {})
            nethunt_folder_id = deal_fields.get(folder_id_key)
            nethunt_record_id = deal_fields.get(record_id_key)
            nethunt_team_record_id = deal_fields.get(team_record_id_key)
            
            
            mapped_fields = extract_person_data_for_nethunt(deal_data)
            team_mapped_fields = extract_team_data_for_nethunt(deal_data)
            logging.info(f"Mapped fields for NetHunt: {mapped_fields}")

            if not nethunt_folder_id or not nethunt_record_id:
                logging.warning(f"NetHunt folder or record ID not found in deal {deal_id}")
                return
            

            logging.info(f"NetHunt folder_id: {nethunt_folder_id}, record_id: {nethunt_record_id}, team_record_id: {nethunt_team_record_id}")

        # ------------------------
        # Proceed to update NetHunt record
        # ------------------------
        
        email = NETHUNT_EMAIL
        api_key = NETHUNT_API_KEY
        if nethunt_record_id:
            credentials = f"{email}:{api_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            logging.info(f"Updating NetHunt record {nethunt_record_id} with fields: {mapped_fields} and the api key {encoded_credentials}")
            update_nethunt_record(nethunt_record_id, mapped_fields, encoded_credentials)
        if nethunt_team_record_id:
            credentials = f"{email}:{api_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            logging.info(f"Updating NetHunt record {nethunt_team_record_id} with fields: {team_mapped_fields} and the api key {encoded_credentials}")
            update_nethunt_record(nethunt_team_record_id, team_mapped_fields, encoded_credentials)


    
# ALLOWED_FIELDS = {
#     "Name": "Name",
#     "email": "Email",
#     "phone": "Phone",
#     "Stage": "Stage",
#     "Pipeline": "Pipeline",
#     "b4657a3853fbae1a21222a1f6265dffd1111fc55": "First Name", 
#     "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "Address",
#     # "fb3c253d2c30416d52191beb3c443f96133c571c": "West Chester Availablity",
#     # "4f01b3626ca1c664c9dec11aad381c405e73bc5d": "Philadelphia Availability",
#     # "4d7a7e1d75b47934b2734ca8d4e270b5e80dd40f": "Main Line Availability",
#     "fe16f95ae1442816f87a9c4ee18b5056f8743030": "Preferred Days / Availability",
#     "e042a0ac93f8d43206b3a96cbe21f24610b74276": "Chef Assigned",
#     "d64ea5791d2efd1b160cba0b4dde0d997d1b513d": "Home Assistant Assigned",
#     "73950ad98eab1e4948d742be2fa34897e457a2f4": "Past Providers",
#     # "3d5c1f11c39686c2d445c279f00ee873c3aa5847": "Services Recieved",
#     "ac2082c8795591a9fb4c4ee0ee6062a11daea132": "Service Interest",
#     "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Last name"
# }

def extract_person_data_for_nethunt(deal_data):
    # Mapping of Pipedrive field keys to NetHunt field names
    key_mapping = {
        # "b4657a3853fbae1a21222a1f6265dffd1111fc55": "First Name", 
    "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "Address",
    # "fb3c253d2c30416d52191beb3c443f96133c571c": "West Chester Availablity",
    # "4f01b3626ca1c664c9dec11aad381c405e73bc5d": "Philadelphia Availability",
    # "4d7a7e1d75b47934b2734ca8d4e270b5e80dd40f": "Main Line Availability",
    "fe16f95ae1442816f87a9c4ee18b5056f8743030": "Preferred Days / Availability",
    "e042a0ac93f8d43206b3a96cbe21f24610b74276": "Chef Assigned",
    "d64ea5791d2efd1b160cba0b4dde0d997d1b513d": "Home Assistant Assigned",
    "73950ad98eab1e4948d742be2fa34897e457a2f4": "Past Providers",
    # "3d5c1f11c39686c2d445c279f00ee873c3aa5847": "Services Recieved",
    "ac2082c8795591a9fb4c4ee0ee6062a11daea132": "Service Interest",
    "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Last name"
    }

    data = deal_data.get("data", {})
    related = deal_data.get("related_objects", {})

    extracted = {}

    # Extract from person
    person = data.get("person_id", {})
    extracted["Name"] = person.get("name", "")
    
    extracted["Email"] = [
        email.get("value") for email in person.get("email", []) if email.get("value")
    ]

    extracted["Phone"] = [
        phone.get("value") for phone in person.get("phone", []) if phone.get("value")
    ]

    extracted["Client Lost Reasons"] = [
        lost_reason.get("value") for lost_reason in person.get("lost_reason", []) if lost_reason.get("value")
    ]

    # Extract stage and pipeline
    stage_id = data.get("stage_id")
    stage_name = ""

    if stage_id is not None:
        stage_info = related.get("stage", {}).get(str(stage_id), {})
        stage_name = stage_info.get("name", "")

# Extract pipeline name
    pipeline_id = data.get("pipeline_id")
    pipeline_name = ""

    if pipeline_id is not None:
        pipeline_info = related.get("pipeline", {}).get(str(pipeline_id), {})
        pipeline_name = pipeline_info.get("name", "")

    # Store extracted values
    extracted["Stage"] = stage_name
    extracted["Pipeline"] = pipeline_name

    # Add placeholder for Client Status
    extracted["Client Status"] = ""

    # Extract custom fields by key
    for key, label in key_mapping.items():
        extracted[label] = data.get(key, "")

    # Build final fieldActions payload
    field_actions = {
        key: {
            "overwrite": True,
            "add": value if value else ""
        } for key, value in extracted.items()
    }

    return {"fieldActions": field_actions}

def extract_team_data_for_nethunt(deal_data):
    # Mapping of Pipedrive field keys to NetHunt field names
    key_mapping = {
        # "b4657a3853fbae1a21222a1f6265dffd1111fc55": "First Name", 
        "ec3c9109c278d7cb22cd6d63187fb63b9c03af21": "Address",
        "fb3c253d2c30416d52191beb3c443f96133c571c": "West Chester Area Availability",
        "4f01b3626ca1c664c9dec11aad381c405e73bc5d": "Philadelphia Availability",
        "4d7a7e1d75b47934b2734ca8d4e270b5e80dd40f": "Main Line Availability",
        "fe16f95ae1442816f87a9c4ee18b5056f8743030": "Preferred Days / Availability",
        "71b7dcc1f0a176ed854b4eb3c2eaa7bf33070908": "Last name"
    }

    data = deal_data.get("data", {})
    related = deal_data.get("related_objects", {})

    extracted = {}

    # Extract from person
    person = data.get("person_id", {})
    extracted["Name"] = person.get("name", "")
    
    extracted["Email Primary"] = [
        email.get("value") for email in person.get("email", []) if email.get("value")
    ]

    extracted["Phone"] = [
        phone.get("value") for phone in person.get("phone", []) if phone.get("value")
    ]

    extracted["Lost Reason"] = [
        lost_reason.get("value") for lost_reason in person.get("lost_reason", []) if lost_reason.get("value")
    ]

    # Extract stage and pipeline
    stage_id = data.get("stage_id")
    stage_name = ""

    if stage_id is not None:
        stage_info = related.get("stage", {}).get(str(stage_id), {})
        stage_name = stage_info.get("name", "")

    # Extract pipeline name
    pipeline_id = data.get("pipeline_id")
    pipeline_name = ""

    if pipeline_id is not None:
        pipeline_info = related.get("pipeline", {}).get(str(pipeline_id), {})
        pipeline_name = pipeline_info.get("name", "")

    # Store extracted values
    extracted["Stage"] = stage_name
    extracted["Pipeline"] = pipeline_name

    # Add placeholder for Client Status

    # Extract custom fields by key
    for key, label in key_mapping.items():
        extracted[label] = data.get(key, "")

    # Build final fieldActions payload
    field_actions = {
        key: {
            "overwrite": True,
            "add": value if value else ""
        } for key, value in extracted.items()
    }

    print("Extracted team data for NetHunt: ", field_actions)
    return {"fieldActions": field_actions}



def update_nethunt_record(record_id: str, field_actions: dict, api_key: str):
    url = f"https://nethunt.com/api/v1/zapier/actions/update-record/{record_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {api_key}"
    }

    payload = field_actions  

    print("Updating NetHunt record with payload:")
    print(json.dumps(payload, indent=2)) 

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()