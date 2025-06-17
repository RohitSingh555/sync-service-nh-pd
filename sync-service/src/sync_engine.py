# src/sync_engine.py
import requests
import base64
import httpx
import logging
from src.clients.nethunt import nethunt_client


# Nethunt

EMAIL = "agilemorphsolutions@gmail.com"
API_KEY = "30741f0a-d62d-4703-b0d4-0a03fe6f8782"

BASE_URL = "https://nethunt.com/api/v1/zapier/actions/update-record"

def get_auth_header(email: str, api_key: str):
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

async def update_nethunt_record(record_id: str, fields: dict):
    """
    Update a NetHunt record by its ID with the given field actions.

    :param record_id: NetHunt Record ID
    :param fields: Dictionary of fields to update in the format:
        {
            "Name": {"overwrite": True, "add": "John Doe"},
            "Priority": {"remove": "", "add": "High"},
        }
    """
    url = f"{BASE_URL}/{record_id}"
    headers = {
        "Content-Type": "application/json",
        **get_auth_header(EMAIL, API_KEY)
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


# PIPEDRIVE_API


PIPEDRIVE_API_TOKEN = "e68c1501ba119489fc7690a81488e504f7c530f4"
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"

async def handle_activity_webhook(body: dict):
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

        mapped_fields = extract_person_data_for_nethunt(person_data)
        logging.info(f"Mapped fields for NetHunt: {mapped_fields}")

        # ------------------------
        # Deal fetch and folder/record ID extraction
        # ------------------------
        deal_id = current.get("deal_id")
        nethunt_folder_id = None
        nethunt_record_id = None

        if deal_id:
            deal_url = f"{PIPEDRIVE_BASE_URL}/deals/{deal_id}"
            deal_response = await client.get(deal_url, headers=headers)

            if deal_response.status_code != 200:
                logging.error(f"Failed to fetch deal {deal_id}: {deal_response.status_code} - {deal_response.text}")
                return

            deal_data = deal_response.json()
            logging.info(f"Deal data for ID {deal_id}: {deal_data}")

            # Hardcoded keys
            record_id_key = "55eb66f5d38ea77a03e23d3f0f3dd31b891739d1"
            folder_id_key = "6cff18ff6ad02610ded066fab268f76d7d6431c9"

            deal_fields = deal_data.get("data", {})
            nethunt_folder_id = deal_fields.get(folder_id_key)
            nethunt_record_id = deal_fields.get(record_id_key)

            if not nethunt_folder_id or not nethunt_record_id:
                logging.warning(f"NetHunt folder or record ID not found in deal {deal_id}")
                return

            logging.info(f"NetHunt folder_id: {nethunt_folder_id}, record_id: {nethunt_record_id}")

        # ------------------------
        # Proceed to update NetHunt record
        # ------------------------
        if nethunt_record_id:
            email = "agilemorphsolutions@gmail.com"
            api_key = "30741f0a-d62d-4703-b0d4-0a03fe6f8782"
            credentials = f"{email}:{api_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            # Make sure this function is async and awaitable
            await update_nethunt_record(nethunt_record_id, mapped_fields, encoded_credentials)

import json

def extract_person_data_for_nethunt(pipedrive_data: dict) -> str:
    """Return NetHunt-compatible fieldActions as a JSON string with proper key quotes."""
    data = pipedrive_data.get("data", {})

    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    priority = data.get("priority", "")
    creator = data.get("owner_name", "")
    assignee = data.get("user_id", {}).get("name", "") if isinstance(data.get("user_id"), dict) else ""
    due_date = data.get("next_activity_date", "")
    description = data.get("notes", "")

    field_actions = {
        "Name": {"overwrite": True, "add": name},
        "Priority": {"overwrite": True, "add": priority},
        "Description": {"overwrite": False, "add": description},
        "All day": {"overwrite": True, "add": False}
    }

    return json.dumps(field_actions, ensure_ascii=False, indent=2)



def update_nethunt_record(record_id, field_actions, api_key):
    url = f"https://nethunt.com/api/v1/zapier/actions/update-record/{record_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {api_key}"
    }

    payload = {
        "fieldActions": field_actions
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()
