# tasks.py

from state import get_last_poll, set_last_poll

async def poll_nethunt(interval_seconds: int):
    while True:
        last_poll = get_last_poll()
        recent_records = await nethunt_client.get_recent_records(last_poll)
        if recent_records:
            await sync_nethunt_records(recent_records)
        set_last_poll(int(asyncio.time()))
        await asyncio.sleep(interval_seconds)
