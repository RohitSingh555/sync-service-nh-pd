# src/sync_engine.py
import requests
import base64
import httpx
import logging
import os
import json
from dotenv import load_dotenv
from src.create_activity import format_due_date_iso, nethunt_activity_exists_by_name_returns_results
load_dotenv()



# Nethunt
NETHUNT_API_KEY = os.getenv("NETHUNT_API_KEY")
NETHUNT_EMAIL = os.getenv("NETHUNT_EMAIL")
PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")

BASE_URL = "https://nethunt.com/api/v1/zapier/actions/update-record"

def get_auth_header(email: str, api_key: str):
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

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


# PIPEDRIVE_API
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"

async def handle_activity_update_webhook(body: dict):
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

    # Always re-fetch the full activity details
    full_activity = await fetch_pipedrive_activity_by_id(activity_id)
    if not full_activity:
        logging.warning(f"Could not fetch full activity data for ID {activity_id}")
        return

    logging.debug(f"Full activity data: {full_activity}")

    # Extract mapped fields from full activity
    try:
        mapped_fields = extract_activity_data_for_nethunt(full_activity)
        logging.info(f"Mapped fields for NetHunt Update: {mapped_fields}")
    except Exception as e:
        logging.error(f"Error mapping activity fields for NetHunt Update: {e}")
        return

    nethunt_record = await nethunt_activity_exists_by_name_returns_results(full_activity.get("subject"))

    # -----------------------
    # Proceed to update NetHunt record
    # ------------------------
    if nethunt_record:
        print(f"Updating NetHunt record {nethunt_record[0].get("id")} with fields: {mapped_fields}")
        try:
            credentials = f"{NETHUNT_EMAIL}:{NETHUNT_API_KEY}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            update_nethunt_record(nethunt_record[0].get("id"), mapped_fields, encoded_credentials)
            logging.info(f"NetHunt record {nethunt_record[0].get("id")} updated successfully.")
        except Exception as e:
            logging.error(f"Failed to update NetHunt record {nethunt_record[0].get("id")}: {e}")


def extract_person_data_for_nethunt(pipedrive_data: dict) -> str:
    """Return NetHunt-compatible fieldActions as a JSON string with proper key quotes."""
    data = pipedrive_data.get("data", {})

    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    priority = data.get("priority", "")
    due_date = data.get("due_date")
    formatted_due_date = format_due_date_iso(due_date) if due_date else None
    description = data.get("notes", "")

    field_actions = {
        "Name": {"overwrite": True, "add": name},
        "Priority": {"overwrite": True, "add": priority},
        "Description": {"overwrite": False, "add": description},
        "All day": {"overwrite": True, "add": False},
        "Due date": formatted_due_date,
    }

    return json.dumps(field_actions, ensure_ascii=False, indent=2)

def map_nethunt_to_pipedrive_activity(nethunt_record: dict, deal_ids: list[str], person_ids: list[str]) -> dict:
    fields = nethunt_record.get("fields", {})
    deal_id = int(deal_ids[0]) if deal_ids else None
    person_id = int(person_ids[0]) if person_ids else None
    print(f"Mapping NetHunt record to Pipedrive activity: {fields}, deal_id: {deal_id}, person_id {person_id}")

    priority_reverse_map = {
        "High": 191,
        "Medium": 190,
        "Low": 189
    }

    priority_label = fields.get("Priority")
    priority = priority_reverse_map.get(priority_label, 189)

    due_date_raw = fields.get("Due date", "")
    due_date = None
    due_time = None

    if "T" in due_date_raw:
        try:
            date_part, time_part = due_date_raw.split("T")
            due_date = date_part
            try:
                time_str = time_part.split("Z")[0].split(".")[0]  # e.g., "15:30:00"
                hh_mm = ":".join(time_str.split(":")[:2])         # Extract "15:30"
                due_time = hh_mm
            except Exception as e:
                due_time = None
                print(f"Failed to extract HH:mm from time: {time_part}, error: {e}")
        except Exception as e:
            print(f"Failed to parse Due date from NetHunt: {due_date_raw}, error: {e}")
    else:
        due_date = due_date_raw or None

    return {
        "subject": fields.get("Name"),
        "note": fields.get("Description"),
        "due_date": due_date,
        "due_time": due_time,
        "deal_id": deal_id,
        "participants": [{"person_id": person_id}],
        "priority": priority,
        "owner_id": 17872313,
        "type": "task",
        "location": None,
        "duration": None,
        "attendees": []
    }


def map_nethunt_person_fields_to_pipedrive(record_fields: dict) -> dict:
    key_mapping = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "phone": "Phone",
        "address": "Address",
    }
    payload = {}
    for pipedrive_key, field_name in key_mapping.items():
        if field_name in record_fields:
            value = record_fields[field_name]
            if isinstance(value, list):
                value = value[0] if value else None
            payload[pipedrive_key] = value
    print(f"Mapped person fields for Pipedrive update: {payload}")
    return payload

def map_nethunt_to_pipedrive_activity_no_deal(nethunt_record: dict) -> dict:
    fields = nethunt_record.get("fields", {})
    print(f"Mapping NetHunt record to Pipedrive activity (update): {fields}")

    # Reverse map from label to numeric priority
    priority_reverse_map = {
        "High": 191,
        "Medium": 190,
        "Low": 189
    }

    priority_label = fields.get("Priority")
    priority = priority_reverse_map.get(priority_label, 189)

    due_date_raw = fields.get("Due date", "")
    due_date = None
    due_time = None

    if "T" in due_date_raw:
        try:
            date_part, time_part = due_date_raw.split("T")
            due_date = date_part
            due_time = time_part.split("Z")[0].split(".")[0]
        except Exception as e:
            print(f"Failed to parse Due date from NetHunt: {due_date_raw}, error: {e}")
    else:
        due_date = due_date_raw or None

    return {
        "note": fields.get("Description"),
        "due_date": due_date,
        "priority": priority,
        "priority": priority
    }


def update_nethunt_record(record_id, field_actions, api_key):
    url = f"https://nethunt.com/api/v1/zapier/actions/update-record/{record_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {api_key}"
    }


    response = requests.post(url, headers=headers, json=field_actions)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()


async def create_pipedrive_activity(activity_data: dict):
    url = f"https://api.pipedrive.com/api/v2/activities"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-token": PIPEDRIVE_API_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=activity_data)
            response.raise_for_status()
            result = response.json()
            logging.info(f"Created activity in Pipedrive: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to create activity: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error during activity creation: {e}")


import re
import json
import logging

def extract_activity_data_for_nethunt(activity: dict) -> dict:
    try:
        subject = activity.get("subject")
        due_date = activity.get("due_date")
        user_id = activity.get("user_id")
        is_done = activity.get("done", False)
        note = activity.get("note") or ""
        priority_value = activity.get("priority")

        # Priority mapping
        priority = {191: "High", 190: "Medium"}.get(priority_value, "Low")

        # Format due date
        formatted_due_date = format_due_date_iso(due_date) if due_date else None

        # Assignee (hardcoded as of now)
        target_email = "contact@elevated-lifestyle.com"
        assignee = [target_email]

        logging.debug(f"Mapping activity to NetHunt fields: subject='{subject}', due_date='{due_date}', assignee={assignee}, priority='{priority}'")

        # Build fieldActions
        field_actions = {
            "Due date": {
                "overwrite": True,
                "add": formatted_due_date
            },
            "Description": {
                "overwrite": True,
                "add": note
            },
            "Priority": {
                "overwrite": True,
                "add": priority
            }
        }

        # Add assignee if available
        if assignee:
            field_actions["Assignee"] = {
                "overwrite": True,
                "add": assignee
            }

        print(f"Extracted field actions for NetHunt: {field_actions}")  
        return {
            "fieldActions": field_actions
        }

    except Exception as e:
        logging.error(f"Error extracting fields for NetHunt: {e}")
        raise


async def fetch_pipedrive_activity_by_id(activity_id: int) -> dict | None:

    url = f"{PIPEDRIVE_BASE_URL}/activities/{activity_id}"
    headers = {
        "x-api-token": PIPEDRIVE_API_TOKEN,
        "Accept": "application/json"
    }
    params = {}

    logging.debug(f"Fetching activity ID={activity_id} ")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            logging.debug(f"Pipedrive GET {url} - status {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logging.debug(f"Fetched activity {activity_id} data: {result}")
            return result.get("data")
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching activity {activity_id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error fetching activity {activity_id}: {e}")
    return None

async def update_pipedrive_activity(activity_id: int, activity_data: dict):
    url = f"https://api.pipedrive.com/api/v2/activities/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-token": PIPEDRIVE_API_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.patch(url, headers=headers, json=activity_data)
            response.raise_for_status()
            result = response.json()
            logging.info(f"Updated Pipedrive activity {activity_id}: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to update activity {activity_id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error during activity update {activity_id}: {e}")
