# main.py
import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import json

import httpx

from src.sync_engine import handle_activity_webhook
from src.sync_deals_to_services_engine import handle_deals_webhook
from src.clients.nethunt import nethunt_client
from src.state import get_last_poll, set_last_poll
from src.update_pipedrive_data import map_nethunt_fields_to_pipedrive, update_pipedrive_deal

# Configure logging to write to a fil
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("error_logs.txt"),
        logging.StreamHandler()
    ]
)

async def poll_nethunt(interval_seconds=65):
    folder_ids = [
        "67e2c9a38fe9ca14e35144d2",
        "67e17578cc9bea52af34a26f"
    ]

    while True:
        try:
            last_poll = get_last_poll()
            logging.info(f"Polling NetHunt with since={last_poll}")
            latest_updated_at = None

            for folder_id in folder_ids:
                params = {
                    "folder_id": folder_id,
                    "since": last_poll,
                    "limit": 100
                }

                recent_records = await nethunt_client.get_recent_records(**params)

                if recent_records:
                    logging.debug(f"Fetched {len(recent_records)} records from folder {folder_id}")
                    logging.debug(f"Record data: {json.dumps(recent_records, indent=2)}")

                    for record in recent_records:
                        fields = record.get("fields", {})
                        pipedrive_id = fields.get("Pipedrive Record ID")

                        if pipedrive_id:
                            logging.info(f"Found Pipedrive Record ID: {pipedrive_id} in record {record.get('id')}")
                            payload = map_nethunt_fields_to_pipedrive(fields)
                            await update_pipedrive_deal(pipedrive_id, payload)

                        updated_at = record.get("updatedAt")
                        if updated_at and (latest_updated_at is None or updated_at > latest_updated_at):
                            latest_updated_at = updated_at

            # Save and log the latest updatedAt value exactly as receive
            if latest_updated_at:
                logging.info(f"Saving latest updatedAt string as-is: {latest_updated_at}")
                set_last_poll(latest_updated_at)

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error in poll_nethunt: {e.response.status_code} - {e.response.text}")
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
async def activity_webhook(req: Request):
    try:
        body = await req.json()
        logging.debug(f"Received activity webhook payload: {body}")
        await handle_activity_webhook(body)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error in /webhook/activity: {e}")
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
