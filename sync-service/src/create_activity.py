import os
import logging
import httpx
from dotenv import load_dotenv
from src.sync_deals_to_services_engine import get_auth_header

# Load environment variables from .env file
load_dotenv()

NETHUNT_API_KEY = os.getenv("NETHUNT_API_KEY")
NETHUNT_EMAIL = os.getenv("NETHUNT_EMAIL")
NETHUNT_TASKS_FOLDER_ID = "67e17578cc9bea52af34a271"
NETHUNT_BASE_URL = "https://nethunt.com/api/v1"
PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"

headers = {
    "Content-Type": "application/json",
    **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
}


from datetime import datetime
import urllib.parse
def format_due_date_iso(due_date_str: str) -> str:
    try:
        dt = datetime.strptime(due_date_str, "%Y-%m-%d")
        return dt.isoformat() + "Z"
    except Exception as e:
        logging.warning(f"Could not parse due date: {due_date_str}. Error: {e}")
        return None

async def nethunt_activity_exists_by_name(name: str) -> bool:
    # Construct raw query
    raw_query = f'"Name":"{name}"'
    encoded_query = urllib.parse.quote(raw_query)

    # Manually construct full URL with encoded query
    full_url = f"{NETHUNT_BASE_URL}/zapier/searches/find-record/{NETHUNT_TASKS_FOLDER_ID}?query={encoded_query}"

    headers = {
        "Content-Type": "application/json",
        **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
    }

    async with httpx.AsyncClient() as client:
        try:
            logging.debug(f"NetHunt search request sent to {full_url}")
            response = await client.get(full_url, headers=headers)
            response.raise_for_status()
            results = response.json()
            logging.debug(f"NetHunt search response: {results}")
            return bool(results)
        except Exception as e:
            logging.warning(f"Error checking existing record by Name in NetHunt: {e}")
            return False
        
async def nethunt_activity_exists_by_name_returns_results(name: str) -> bool:
    # Construct raw query
    raw_query = f'"Name":"{name}"'
    encoded_query = urllib.parse.quote(raw_query)

    # Manually construct full URL with encoded query
    full_url = f"{NETHUNT_BASE_URL}/zapier/searches/find-record/{NETHUNT_TASKS_FOLDER_ID}?query={encoded_query}"

    headers = {
        "Content-Type": "application/json",
        **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
    }

    async with httpx.AsyncClient() as client:
        try:
            logging.debug(f"NetHunt search request sent to {full_url}")
            response = await client.get(full_url, headers=headers)
            response.raise_for_status()
            results = response.json()
            logging.debug(f"NetHunt search response: {results}")
            return results
        except Exception as e:
            logging.warning(f"Error checking existing record by Name in NetHunt: {e}")
            return False

async def fetch_pipedrive_activity_by_id(activity_id: int) -> dict | None:
    url = f"{PIPEDRIVE_BASE_URL}/activities/{activity_id}"
    headers = {
        "Accept": "application/json",
        "x-api-token": PIPEDRIVE_API_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logging.error(f"Failed to fetch Pipedrive activity {activity_id}: {e}")
            return None

import re
import json

async def process_created_activity(activity: dict):
    subject = activity.get("subject")
    logging.info(f"Starting processing for activity with subject: '{subject}'")

    try:
        exists = await nethunt_activity_exists_by_name(subject)
        logging.debug(f"nethunt_activity_exists_by_name('{subject}') returned: {exists}")
        if exists:
            logging.info(f"Record with subject '{subject}' already exists in NetHunt. Skipping creation.")
            return
    except Exception as e:
        logging.error(f"Error while checking for existing NetHunt record: {e}")
        return

    activity_id = activity.get("id")
    due_date = activity.get("due_date")
    user_id = activity.get("user_id")
    is_done = activity.get("done", False)
    priority_value = activity.get("priority")
    priority = {191: "High", 190: "Medium"}.get(priority_value, "Low")
    note = activity.get("note") or ""
    formatted_due_date = format_due_date_iso(due_date) if due_date else None

    logging.info(f"Processing new activity: ID={activity_id}, Subject='{subject}', Due={due_date}, User ID={user_id}, Priority={priority}, Done={is_done}")

    # Use regex to search for specific email in the entire activity structure
    target_email = "contact@elevated-lifestyle.com"
    activity_str = json.dumps(activity)
    assignee = ["contact@elevated-lifestyle.com"]
    logging.info(f"Extracted assignee email: {assignee if assignee else 'None found'}")

    # Fetch NetHunt linked record from deal_id
    deal_id = activity.get("deal_id")
    try:
        linked_record_id = await fetch_nethunt_record_id_by_deal_id(deal_id)
        logging.debug(f"Linked NetHunt record ID from deal_id '{deal_id}': {linked_record_id}")
    except Exception as e:
        logging.error(f"Failed to fetch linked NetHunt record from deal_id {deal_id}: {e}")
        linked_record_id = None

    fields = {
        "Name": subject,
        "Due date": formatted_due_date,
        "Completed": is_done,
        "Creator": str(user_id),
        "Description": note,
        "All day": True,
        "Assignee": ["Marie <contact@elevated-lifestyle.com>"],
        "Priority": priority
    }

    if linked_record_id:
        fields["Record links"] = [linked_record_id]

    data = {
        "timeZone": "Europe/London",
        "fields": fields
    }

    url = f"{NETHUNT_BASE_URL}/zapier/actions/create-record/{NETHUNT_TASKS_FOLDER_ID}"

    async with httpx.AsyncClient() as client:
        try:
            logging.debug(f"Sending POST request to NetHunt to create task: {json.dumps(data, indent=2)}")
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            logging.info(f"Successfully created record in NetHunt: {result}")
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to create record in NetHunt: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error creating record in NetHunt: {e}")

async def fetch_person_email_from_pipedrive(person_id: int) -> str | None:
    if not person_id:
        logging.warning("No person_id provided.")
        return None

    try:
        pipedrive_headers = {
            "Accept": "application/json",
            "x-api-token": PIPEDRIVE_API_TOKEN
        }

        person_url = f"{PIPEDRIVE_BASE_URL}/persons/{person_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(person_url, headers=pipedrive_headers)
            if response.status_code != 200:
                logging.warning(f"Failed to fetch person {person_id}: {response.status_code} - {response.text}")
                return None

            person_data = response.json()
            logging.info(f"Fetched person data for ID {person_id}: {person_data}")

            emails = person_data.get("data", {}).get("email", [])
            if emails:
                return emails[0].get("value")

            logging.info(f"No email found for person {person_id}")
            return None

    except Exception as e:
        logging.error(f"Error while fetching person email: {e}")
        return None

async def fetch_nethunt_record_id_by_deal_id(deal_id: int) -> str | None:
    """Searches NetHunt for a record using the Pipedrive Deal ID."""
    if not deal_id:
        logging.warning("No deal_id provided for NetHunt lookup.")
        return None

    encoded_query = f'"Pipedrive Record Id":"{deal_id}"'
    url = f"{NETHUNT_BASE_URL}/zapier/searches/find-record/67e17578cc9bea52af34a26f?query={encoded_query}&limit=10"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()

            logging.debug(f"NetHunt search result for Deal ID {deal_id}: {result}")

            # NetHunt returned a list, not a dict
            if isinstance(result, list) and result:
                record_id = result[0].get("recordId")
                logging.info(f"Found NetHunt record ID for Deal ID {deal_id}: {record_id}")
                return record_id

            logging.warning(f"No NetHunt record found for Deal ID: {deal_id}")
            return None

    except Exception as e:
        logging.error(f"Error fetching NetHunt record by Deal ID {deal_id}: {e}")
        return None

async def fetch_nethunt_record_id_by_deal_id_for_teams(deal_id: int) -> str | None:
    """Searches NetHunt for a record using the Pipedrive Deal ID."""
    if not deal_id:
        logging.warning("No deal_id provided for NetHunt lookup.")
        return None

    encoded_query = f'"Pipedrive Record Id":"{deal_id}"'
    url = f"{NETHUNT_BASE_URL}/zapier/searches/find-record/67e2c9a38fe9ca14e35144d2?query={encoded_query}&limit=10"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()

            logging.debug(f"NetHunt search result for Deal ID {deal_id}: {result}")

            # NetHunt returned a list, not a dict
            if isinstance(result, list) and result:
                record_id = result[0].get("recordId")
                logging.info(f"Found NetHunt record ID for Deal ID {deal_id}: {record_id}")
                return record_id

            logging.warning(f"No NetHunt record found for Deal ID: {deal_id}")
            return None

    except Exception as e:
        logging.error(f"Error fetching NetHunt record by Deal ID {deal_id}: {e}")
        return None
