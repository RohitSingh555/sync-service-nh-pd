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
from src.sync_deals_engine import handle_deals_webhook
from src.clients.nethunt import nethunt_client
from src.state import get_last_poll, set_last_poll

# Configure logging to write to a file
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("error_logs.txt"),
        logging.StreamHandler()
    ]
)

async def poll_nethunt(interval_seconds: int = 60):
    folder_id = "67e17578cc9bea52af34a26f" 
    while True:
        try:
            last_poll = get_last_poll()
            params = {
                "folder_id": folder_id,
                "since": last_poll or "2015-01-01T00:00:00.000Z",
                "limit": 100,
                "field_names": ["Name", "Email"]
            }
            logging.debug(f"Requesting recent records with params: {params}")
            recent_records = await nethunt_client.get_recent_records(**params)
            
            if recent_records:
                logging.info(f"Fetched {len(recent_records)} records from NetHunt.")
                # await sync_nethunt_records(recent_records)

            set_last_poll(int(time.time()))
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error in poll_nethunt: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected error in poll_nethunt: {e}")
        finally:
            await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start NetHunt poller every 15s
    app.state.nh_task = asyncio.create_task(poll_nethunt(15))
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
