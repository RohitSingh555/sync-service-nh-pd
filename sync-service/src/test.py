# src/sync_engine.py
import requests
import base64
import httpx
import logging
import json
import os
from dotenv import load_dotenv
load_dotenv()

NETHUNT_API_KEY = os.getenv("NETHUNT_API_KEY")
NETHUNT_EMAIL = os.getenv("NETHUNT_EMAIL")
PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"

BASE_URL = "https://nethunt.com/api/v1"
def get_auth_header(email: str, api_key: str):
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def fetch_deal_ids_from_record_links(record_links: list[str]) -> list[str]:
    deal_ids = []
    search_url = f"{BASE_URL}/zapier/searches/find-record/67e17578cc9bea52af34a26f"  # Folder ID

    headers = {
        "Content-Type": "application/json",
        **get_auth_header(NETHUNT_EMAIL, NETHUNT_API_KEY)
    }

    async with httpx.AsyncClient() as client:
        for record_id in record_links:
            params = {"recordId": record_id}

            print(f"[DEBUG] Searching for NetHunt record ID: {record_id}")
            try:
                response = await client.get(search_url, headers=headers, params=params)
                print(f"[DEBUG] Response status: {response.status_code}")
                response.raise_for_status()

                result = response.json()
                print(f"[DEBUG] Response JSON: {json.dumps(result, indent=2)}")

                if result and isinstance(result, list):
                    record = result[0]
                    pipedrive_id = record.get("fields", {}).get("Pipedrive Record Id")
                    print(f"[DEBUG] Extracted Pipedrive ID: {pipedrive_id}")
                    if pipedrive_id:
                        deal_ids.append(pipedrive_id)
                else:
                    print(f"[DEBUG] No record found for record ID {record_id}")

            except Exception as e:
                logging.warning(f"Failed to fetch Pipedrive Record ID for record {record_id}: {e}")
                print(f"[ERROR] Exception for record ID {record_id}: {e}")

    return deal_ids



import asyncio

# At the bottom of your script
if __name__ == "__main__":
    asyncio.run(fetch_deal_ids_from_record_links(["684fe601001eaf4b0ca1fd57"]))