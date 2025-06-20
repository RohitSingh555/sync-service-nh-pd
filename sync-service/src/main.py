# main.py
import asyncio
from datetime import datetime, timedelta, timezone
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import json

import httpx

from src.sync_engine import create_pipedrive_activity, handle_activity_update_webhook, map_nethunt_to_pipedrive_activity, map_nethunt_to_pipedrive_activity_no_deal, update_pipedrive_activity
from src.sync_deals_to_services_engine import does_activity_exist, fetch_deal_ids_from_record_links, get_pipedrive_activity_by_subject, handle_deals_webhook
from src.clients.nethunt import nethunt_client
from src.state import get_last_poll, set_last_poll
from src.update_pipedrive_data import map_nethunt_fields_to_pipedrive, update_pipedrive_deal
from src.create_activity import fetch_pipedrive_activity_by_id, process_created_activity

import os
import aiohttp
from dotenv import load_dotenv
load_dotenv()

# Configure logging to write to a fil
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Only logs to console
    ]
)


PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN") 
NETHUNT_TEAM_FOLDER_ID = "67e2c9a38fe9ca14e35144d2" 
NETHUNT_SERVICES_FOLDER_ID = "67e17578cc9bea52af34a26f" 
NETHUNT_TASKS_FOLDER_ID = "67e17578cc9bea52af34a271" 

def parse_iso8601(timestamp_str):
    return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

import asyncio
import logging
from datetime import datetime, timezone, timedelta

async def poll_nethunt(interval_seconds=265):
    folder_ids = [
        NETHUNT_TEAM_FOLDER_ID,
        NETHUNT_SERVICES_FOLDER_ID,
        NETHUNT_TASKS_FOLDER_ID
    ]

    while True:
        try:
            last_poll = get_last_poll()
            logging.info(f"Polling NetHunt with since={last_poll}")
            latest_updated_at = None

            for folder_id in folder_ids:
                # Default polling params
                params = {
                    "folder_id": folder_id,
                    "since": last_poll,
                    "limit": 100
                }

                # Special case for TASKS: use 5 min freshness
                if folder_id == NETHUNT_TASKS_FOLDER_ID:
                    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
                    since_iso = five_min_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                    params["since"] = since_iso
                    logging.info(f"Fetching TASK records with since={since_iso}")
                    
                    # Updated Records for TASKS
                    updated_records = await nethunt_client.get_recent_records(
                        folder_id=NETHUNT_TASKS_FOLDER_ID,
                        since=since_iso,
                        limit=100
                    )
                    if updated_records:

                        logging.info(f"Fetched {len(updated_records)} recently updated task records")

                        for record in updated_records:
                            fields = record.get("fields", {})
                            name = fields.get("Name")
                            if not name:
                                continue

                            try:
                                existing_activity = await get_pipedrive_activity_by_subject(name, PIPEDRIVE_API_TOKEN)
                                if not existing_activity:
                                    logging.info(f"No matching Pipedrive activity found for updated task '{name}'. Skipping.")
                                    continue

                                record_links = fields.get("Record links", [])

                                payload = map_nethunt_to_pipedrive_activity_no_deal(record)
                                await update_pipedrive_activity(existing_activity["id"], payload)
                                logging.info(f"Updated Pipedrive activity {existing_activity['id']} for updated task '{name}'")

                            except Exception as e:
                                logging.error(f"Failed to update activity for task record {record.get('id')}: {e}")
                    # Updated Records for TASKS
                    recent_records = await nethunt_client.get_freshly_created_records(**params)

                    if recent_records:
                        logging.info(f"Fetched {len(recent_records)} task records")

                        # Sort records by createdAt (ascending)
                        recent_records.sort(key=lambda r: r.get("createdAt") or "")

                        for record in recent_records:
                            name = record.get("fields", {}).get("Name")
                            if not name:
                                continue

                            # Check for existing activity
                            if await does_activity_exist(name, PIPEDRIVE_API_TOKEN):
                                logging.info(f"Activity '{name}' already exists. Skipping.")
                                continue

                            try:
                                record_links = record.get("fields", {}).get("Record links", [])
                                deal_ids = await fetch_deal_ids_from_record_links(record_links)
                                activity_payload = map_nethunt_to_pipedrive_activity(record, deal_ids)
                                await create_pipedrive_activity(activity_payload)
                                logging.info(f"Created Pipedrive activity for '{name}'")
                            except Exception as e:
                                logging.error(f"Error processing task record {record.get('id')}: {e}")

                            # Track updatedAt to feed into global poll timestamp
                            updated_at = record.get("updatedAt") or record.get("createdAt")
                            if updated_at:
                                try:
                                    updated_dt = parse_iso8601(updated_at)
                                    if not latest_updated_at or updated_dt > parse_iso8601(latest_updated_at):
                                        latest_updated_at = updated_at
                                except Exception as e:
                                    logging.warning(f"Invalid updatedAt in task record {record.get('id')}: {e}")
                else:
                    # Standard processing for other folders
                    recent_records = await nethunt_client.get_recent_records(**params)
                    logging.info(f"Fetched {len(recent_records)} records from folder {folder_id}")

                    for record in recent_records:
                        fields = record.get("fields", {})
                        pipedrive_id = fields.get("Pipedrive Record ID")

                        if pipedrive_id:
                            payload = map_nethunt_fields_to_pipedrive(fields)
                            await update_pipedrive_deal(pipedrive_id, payload)
                            logging.info(f"Updated Pipedrive deal {pipedrive_id} from record {record.get('id')}")

                        updated_at = record.get("updatedAt") or record.get("createdAt")
                        if updated_at:
                            try:
                                updated_dt = parse_iso8601(updated_at)
                                if not latest_updated_at or updated_dt > parse_iso8601(latest_updated_at):
                                    latest_updated_at = updated_at
                            except Exception as e:
                                logging.warning(f"Invalid updatedAt in record {record.get('id')}: {e}")

            # Save the latest poll time for next run
            if latest_updated_at:
                try:
                    latest_dt = parse_iso8601(latest_updated_at)
                    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                    if latest_dt < one_hour_ago:
                        corrected = one_hour_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                        logging.info(f"latest_updated_at too old ({latest_updated_at}), using {corrected}")
                    else:
                        corrected = latest_updated_at
                        logging.info(f"Updating last poll time to {corrected}")
                    set_last_poll(corrected)
                except Exception as e:
                    logging.error(f"Failed to save last poll timestamp: {e}")
            else:
                logging.info("No updatedAt found — skipping last_poll update.")

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error in poll_nethunt: {e}")
        finally:
            await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start NetHunt poller every 15s
    app.state.nh_task = asyncio.create_task(poll_nethunt(65))
    yield
    # Cleanup on shutdown
    if hasattr(app.state, "nh_task"):
        app.state.nh_task.cancel()
        try:
            await app.state.nh_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.post("/webhook")
async def pd_webhook(req: Request):
    try:
        body = await req.json()
        # Save the received JSON to a file
        with open("latest_response.json", "w") as f:
            json.dump(body, f, indent=4)
        logging.info("Saved latest response to latest_response.json")
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error in /webhook: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/webhook/activity")
async def activity_update_webhook(req: Request):
    try:
        body = await req.json()
        logging.debug(f"Received activity webhook payload: {body}")
        await handle_activity_update_webhook(body)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error in /webhook/activity: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/webhook/activity/created")
async def activity_created_webhook(req: Request):
    try:
        body = await req.json()
        logging.debug(f"Received activity.created webhook payload: {body}")

        activity_data = body.get("data")
        if not activity_data:
            logging.warning("No 'data' field in activity.created webhook.")
            return JSONResponse(status_code=400, content={"error": "'data' field missing"})
        
        
        activity_id = activity_data.get("id")
        the_updated_data = await fetch_pipedrive_activity_by_id(activity_id)
        print(f"Fetched updated activity data first time created: {the_updated_data}")
        await process_created_activity(the_updated_data["data"])

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"Error in /webhook/activity/created: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/webhook/deals")
async def deals_webhook(req: Request):
    try:
        body = await req.json()
        logging.debug(f"Received deals webhook payload: {body}")
        await handle_deals_webhook(body)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error in /webhook/deals: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
