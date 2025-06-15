# src/sync_engine.py

import base64
import httpx
import logging
from src.state import get_nh_by_pd, map_pd_to_nh, map_nh_to_pd, get_pd_by_nh
from src.clients.pipedrive import get_item
from src.clients.nethunt import nethunt_client

FIELD_MAP = {
    "Staff/Candidates": {
        "Labels": "Role",
        "Preferred Days / Availability": "Preferred Days / Availability",
        "Lost Reasons": "Lost Reasons",
        "West Chester Availability": "West Chester Availability",
        "Philadelphia Availability": "Philadelphia Availability",
        "Main Line Availability": "Main Line Availability",
    },
    "Sales/Clients": {
        "Labels": "Contact Status",
        "Lost reasons": "Lost reasons",
        "Chef Assigned": "Chef Assigned",
        "Home Assistant Assigned": "Home Assistant Assigned",
        "Past Providers": "Past Providers",
        "Current Services": "Services Received",
        "Service Interest": "Service Interest",
        "Preferred Days / Availability": "Preferred Days / Availability",
    },
    "General": {
        "First Name": "First Name",
        "Last Name": "Last Name",
        "Email": "Email",
        "Phone": "Phone",
        "Address": "Address",
        "Notes": "Comment",
        "Stage": "Stage",
        "Status": "Status",
        "Pipeline": "Pipeline",
    },
}


async def handle_pd_webhook(body: dict):
    current = body.get("current", {})
    previous = body.get("previous", {})
    entity_type = current.get("type", "General")  # Determine entity type

    pd_id = str(current.get("id"))
    nh_id = get_nh_by_pd(pd_id)  # Lookup SQLite mapping

    # Detect only changed fields
    updated_fields = {
        nh_field: current.get(pd_field)
        for pd_field, nh_field in FIELD_MAP[entity_type].items()
        if current.get(pd_field) != previous.get(pd_field)
    }

    # If no changes, skip
    if not updated_fields:
        return

    if nh_id:
        # Update existing NetHunt record
        await nethunt_client.update_record(nh_id, updated_fields)
    else:
        # Create fallback: search by title
        folder_id = "67e17578cc9bea52af34a271"  # Replace with your folder ID
        since = "2015-01-01T00:00:00.000Z"  # Replace with appropriate timestamp
        matched_records = await nethunt_client.get_recent_records(folder_id, since, limit=1, field_names=["Name"])

        if matched_records:
            matched = matched_records[0]
            nh_id = matched["recordId"]
            await nethunt_client.update_record(nh_id, updated_fields)
        else:
            # Create new NetHunt record
            payload = {
                "name": current.get("title") or current.get("subject"),
                **updated_fields
            }
            nh_id = await nethunt_client.create_record(payload)

        # Store cross-ID
        map_pd_to_nh(pd_id, nh_id)
        map_nh_to_pd(nh_id, pd_id)


async def sync_nethunt_records(records: list[dict]):
    for rec in records:
        nh_id = str(rec["id"])
        pd_id = await get_pd_by_nh(nh_id)
        entity_type = "Deal" if "title" in rec else "Task"

        mapped_fields = {
            pd_key: rec.get(nh_key)
            for pd_key, nh_key in FIELD_MAP[entity_type].items()
            if rec.get(nh_key) is not None
        }

        if pd_id:
            await pipedrive_client.update_item(pd_id, mapped_fields, entity_type)
        else:
            created = await pipedrive_client.create_item(mapped_fields, entity_type)
            pd_id = str(created["id"])

        await map_nh_to_pd(nh_id, pd_id)
        await map_pd_to_nh(pd_id, nh_id)

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

    # Get person_id safely
    person_id = current.get("person_id")
    if not person_id:
        logging.warning(f"No person_id associated with activity {activity_id}")
        return

    # Fetch person data from Pipedrive
    url = f"{PIPEDRIVE_BASE_URL}/persons/{person_id}"
    headers = {
        "Accept": "application/json",
        "x-api-token": PIPEDRIVE_API_TOKEN
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            logging.error(f"Failed to fetch person {person_id}: {response.status_code} - {response.text}")
            return

        person_data = response.json()
        logging.info(f"Person data for ID {person_id}: {person_data}")

        # Extract & map fields for NetHunt
        mapped_fields = extract_person_data_for_nethunt(person_data)

        logging.info(f"Mapped fields for NetHunt: {mapped_fields}")

        # Optionally, update NetHunt record (you must define this function separately)
        # await update_nethunt_record(record_id="<NetHunt_Record_ID>", fields=mapped_fields)

def extract_person_data_for_nethunt(pipedrive_data: dict) -> dict:
    """Extract relevant fields from Pipedrive person data to sync with NetHunt."""
    data = pipedrive_data.get("data", {})

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    notes = data.get("notes")

    email = None
    if data.get("email"):
        email = next((e["value"] for e in data["email"] if e.get("primary")), data["email"][0]["value"])

    phone = None
    if data.get("phone"):
        phone = next((p["value"] for p in data["phone"] if p.get("primary")), data["phone"][0]["value"])

    address = data.get("postal_address_formatted_address") or data.get("postal_address") or ""

    stage = data.get("stage") or ""
    status = data.get("status") or ""
    pipeline = data.get("pipeline") or ""

    return {
        "First Name": {"overwrite": True, "add": first_name or ""},
        "Last Name": {"overwrite": True, "add": last_name or ""},
        "Email": {"overwrite": True, "add": email or ""},
        "Phone": {"overwrite": True, "add": phone or ""},
        "Address": {"overwrite": True, "add": address or ""},
        "Comment (NH)": {"overwrite": True, "add": notes or ""},
        "Stage": {"overwrite": True, "add": stage},
        "Status": {"overwrite": True, "add": status},
        "Pipeline": {"overwrite": True, "add": pipeline}
    }
