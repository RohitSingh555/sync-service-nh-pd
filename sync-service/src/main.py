# main.py
from fastapi import FastAPI, Request, BackgroundTasks
from tasks import poll_nethunt
from sync_engine import handle_pd_webhook

app = FastAPI()

@app.on_event("startup")
async def startup():
    # start NetHunt poller every 15s
    app.state.nh_task = asyncio.create_task(poll_nethunt(15))

@app.on_event("shutdown")
async def shutdown():
    app.state.nh_task.cancel()

@app.post("/webhook")
async def pd_webhook(req: Request):
    body = await req.json()
    await handle_pd_webhook(body)
    return {"status": "ok"}
