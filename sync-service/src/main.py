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

from src.sync_engine import create_pipedrive_activity, handle_activity_update_webhook, map_nethunt_person_fields_to_pipedrive, map_nethunt_to_pipedrive_activity, map_nethunt_to_pipedrive_activity_no_deal, update_pipedrive_activity
from src.sync_deals_to_services_engine import does_activity_exist, fetch_deal_ids_from_record_links, get_pipedrive_activity_by_subject, handle_deals_webhook
from src.clients.nethunt import nethunt_client
from src.state import get_last_poll, set_last_poll, get_last_comment_poll, set_last_comment_poll, is_comment_synced, mark_comment_synced
from src.update_pipedrive_data import map_nethunt_fields_to_pipedrive, update_pipedrive_deal
from src.create_activity import fetch_nethunt_record_id_by_deal_id_for_teams, fetch_pipedrive_activity_by_id, process_created_activity, fetch_nethunt_record_id_by_deal_id

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


async def create_pipedrive_note(deal_id: int, content: str):
    url = f"https://api.pipedrive.com/v1/notes"
    headers = {
        "x-api-token": PIPEDRIVE_API_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "deal_id": deal_id,
        "content": content
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

async def get_pipedrive_notes_for_deal(deal_id: int):
    url = f"https://api.pipedrive.com/v1/notes"
    headers = {
        "x-api-token": PIPEDRIVE_API_TOKEN,
        "Accept": "application/json"
    }
    params = {"deal_id": deal_id}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("data", [])

async def sync_nethunt_comments_to_pipedrive_notes(folder_ids, _):
    last_comment_poll = get_last_comment_poll()
    print(f"[DEBUG] sync_nethunt_comments_to_pipedrive_notes called with folder_ids={folder_ids} and last_comment_poll={last_comment_poll}")
    latest_created_at = None
    for folder_id in folder_ids:
        recent_comments = await nethunt_client.get_recent_comments(folder_id, since=last_comment_poll, limit=10)
        print(f"[DEBUG] Fetched {len(recent_comments)} recent comments from NetHunt folder {folder_id}")
        for comment in recent_comments:
            comment_id = comment.get("commentId")
            record_id = comment.get("recordId")
            comment_text = comment.get("text")
            created_at = comment.get("createdAt")
            if not comment_id or not record_id or not comment_text:
                print(f"Skipping comment with missing commentId, recordId or text: {comment}")
                continue
            if is_comment_synced(comment_id):
                print(f"Comment {comment_id} already synced, skipping.")
                continue
            # Fetch the record to get the Pipedrive deal id
            records = await nethunt_client.get_recent_records(folder_id, since=last_comment_poll, limit=1, field_names=None)
            record = next((r for r in records if r.get("recordId") == record_id), None)
            if not record:
                print(f"No NetHunt record found for recordId {record_id}")
                continue
            fields = record.get("fields", {})
            pipedrive_deal_id = fields.get("Pipedrive Record ID")
            if pipedrive_deal_id:
                try:
                    # Check if note already exists in Pipedrive for this deal
                    existing_notes = await get_pipedrive_notes_for_deal(pipedrive_deal_id)
                    if any(note.get("content") == comment_text for note in existing_notes):
                        print(f"Note already exists in Pipedrive for deal {pipedrive_deal_id}, skipping creation.")
                        logging.info(f"Skipping duplicate note for deal {pipedrive_deal_id} (already exists in Pipedrive)")
                        mark_comment_synced(comment_id, created_at, record_id)
                        continue
                    await create_pipedrive_note(pipedrive_deal_id, comment_text)
                    logging.info(f"Created Pipedrive note for deal {pipedrive_deal_id} from NetHunt comment {comment_id}")
                    mark_comment_synced(comment_id, created_at, record_id)
                except Exception as e:
                    print(f"Failed to create Pipedrive note for deal {pipedrive_deal_id}: {e}")
                    logging.error(f"Failed to create Pipedrive note for deal {pipedrive_deal_id}: {e}")
            else:
                print(f"No Pipedrive deal ID found in NetHunt record fields for recordId {record_id}")
            # Track the latest createdAt
            if created_at:
                if not latest_created_at or created_at > latest_created_at:
                    latest_created_at = created_at
    # After processing all comments, update the last comment poll time
    if latest_created_at:
        from datetime import datetime, timedelta
        import dateutil.parser
        dt = dateutil.parser.isoparse(latest_created_at) + timedelta(seconds=2)
        # Format as ISO8601 with milliseconds and Z
        corrected = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        set_last_comment_poll(corrected)
        print(f"[DEBUG] Updated last_nethunt_comment_poll to {corrected}")

async def poll_nethunt(interval_seconds=265):
    folder_ids = [
        NETHUNT_TEAM_FOLDER_ID,
        NETHUNT_SERVICES_FOLDER_ID,
        NETHUNT_TASKS_FOLDER_ID
    ]


    while True:
        try:
            last_poll = get_last_poll()
            logging.info(f"[poll_nethunt] Polling NetHunt with since={last_poll}")
            latest_updated_at = None
            
            await sync_nethunt_comments_to_pipedrive_notes(folder_ids, last_poll)
            for folder_id in folder_ids:
                params = {
                    "folder_id": folder_id,
                    "since": last_poll,
                    "limit": 100
                }

                if folder_id == NETHUNT_TASKS_FOLDER_ID:
                    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
                    since_iso = five_min_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                    params["since"] = since_iso
                    logging.info(f"[poll_nethunt] Fetching TASK records with since={since_iso}")
                    
                    updated_records = await nethunt_client.get_recent_records(
                        folder_id=NETHUNT_TASKS_FOLDER_ID,
                        since=since_iso,
                        limit=100
                    )
                    if updated_records:
                        logging.info(f"[poll_nethunt] Got {len(updated_records)} updated task records")
                        for record in updated_records:
                            fields = record.get("fields", {})
                            name = fields.get("Name")
                            if not name:
                                continue
                            try:
                                existing_activity = await get_pipedrive_activity_by_subject(name, PIPEDRIVE_API_TOKEN)
                                if not existing_activity:
                                    continue
                                payload = map_nethunt_to_pipedrive_activity_no_deal(record)
                                await update_pipedrive_activity(existing_activity["id"], payload)
                            except Exception as e:
                                logging.error(f"[poll_nethunt] Error updating activity for task record {record.get('id')}: {e}")
                    recent_records = await nethunt_client.get_freshly_created_records(**params)
                    if recent_records:
                        logging.info(f"[poll_nethunt] Got {len(recent_records)} new task records")
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
                                deal_ids, person_ids = await fetch_deal_ids_from_record_links(record_links)
                                activity_payload = map_nethunt_to_pipedrive_activity(record, deal_ids, person_ids)
                                await create_pipedrive_activity(activity_payload)
                            except Exception as e:
                                logging.error(f"[poll_nethunt] Error processing task record {record.get('id')}: {e}")
                            updated_at = record.get("updatedAt") or record.get("createdAt")
                            if updated_at:
                                try:
                                    updated_dt = parse_iso8601(updated_at)
                                    if not latest_updated_at or updated_dt > parse_iso8601(latest_updated_at):
                                        latest_updated_at = updated_at
                                except Exception as e:
                                    logging.warning(f"[poll_nethunt] Invalid updatedAt in task record {record.get('id')}: {e}")
                else:
                    recent_records = await nethunt_client.get_recent_records(
                        folder_id=folder_id,
                        since=params["since"],
                        limit=params["limit"]
                    )
                    print(f"recent_records: {recent_records}")
                    logging.info(f"[poll_nethunt] Got {len(recent_records)} records from folder {folder_id}")
                    for record in recent_records:
                        fields = record.get("fields", {})
                        logging.info(f"Fields received from NetHunt: {list(fields.keys())}")
                        pipedrive_id = fields.get("Pipedrive Record ID")
                        person_id = fields.get("Pipedrive Person ID")
                        logging.info(f"Extracted pipedrive_id: {pipedrive_id}, person_id: {person_id}")
                        if person_id:
                            person_payload = map_nethunt_person_fields_to_pipedrive(record)
                            await update_pipedrive_person_v2(person_id, person_payload, PIPEDRIVE_API_TOKEN)
                        if pipedrive_id:
                            payload = map_nethunt_fields_to_pipedrive(fields)
                            await update_pipedrive_deal(pipedrive_id, payload)
                        updated_at = record.get("updatedAt") or record.get("createdAt")
                        if updated_at:
                            try:
                                updated_dt = parse_iso8601(updated_at)
                                if not latest_updated_at or updated_dt > parse_iso8601(latest_updated_at):
                                    latest_updated_at = updated_at
                            except Exception as e:
                                logging.warning(f"[poll_nethunt] Invalid updatedAt in record {record.get('id')}: {e}")

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

@app.post("/webhook/notes")
async def webhook_notes(req: Request):
    try:
        body = await req.json()
        logging.info(f"Received notes webhook payload: {body}")
        data = body.get("data", {})
        note_text = data.get("content")
        deal_id = data.get("deal_id")
        if not deal_id or not note_text:
            return JSONResponse(status_code=400, content={"error": "'deal_id' and 'content' are required in 'data'"})
        record_id = await fetch_nethunt_record_id_by_deal_id(deal_id)
        teams_record_id = await fetch_nethunt_record_id_by_deal_id_for_teams(deal_id)
        if not record_id:
            return JSONResponse(status_code=404, content={"error": f"No NetHunt record found for deal_id {deal_id}"})
        # Check for duplicate comment in NetHunt before creating
        record_comments = await get_nethunt_record_comments(record_id)
        if any(c.get("text") == note_text for c in record_comments):
            logging.info(f"Comment already exists in NetHunt record {record_id}, skipping creation.")
            return {"status": "skipped", "reason": "duplicate comment in NetHunt"}
        result = await nethunt_client.create_comment(record_id, note_text)
        # Also check and create for teams_record_id if needed
        if teams_record_id:
            team_comments = await get_nethunt_record_comments(teams_record_id)
            if not any(c.get("text") == note_text for c in team_comments):
                await nethunt_client.create_comment(teams_record_id, note_text)
        return result
    except Exception as e:
        logging.error(f"Error in /webhook/notes: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

async def update_pipedrive_person_v2(person_id: int, payload: dict, api_token: str) -> dict:
    """
    Sends a PATCH request to Pipedrive v2 /api/v2/persons/{id} to update a person.
    """
    url = f"https://api.pipedrive.com/api/v2/persons/{person_id}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    params = {"api_token": api_token}
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        return response.json()

async def get_nethunt_record_comments(record_id: str):
    # Fetch all comments for a NetHunt record using the API
    # GET /zapier/triggers/new-comment/{folderId}?since=1970-01-01T00:00:00.000Z&limit=1000
    all_comments = []
    for folder_id in [NETHUNT_TEAM_FOLDER_ID, NETHUNT_SERVICES_FOLDER_ID, NETHUNT_TASKS_FOLDER_ID]:
        comments = await nethunt_client.get_recent_comments(folder_id, since="1970-01-01T00:00:00.000Z", limit=1000)
        all_comments.extend([c for c in comments if c.get("recordId") == record_id])
    return all_comments