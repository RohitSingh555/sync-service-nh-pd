# clients/pipedrive.py
import httpx, asyncio
from aiolimiter import AsyncLimiter

# Define PIPEDRIVE configuration
PIPEDRIVE = {
    "api_token": "e68c1501ba119489fc7690a81488e504f7c530f4",  # Replace with your Pipedrive API token
    "bucket_capacity": 40,         # Maximum requests per time period
}

limiter = AsyncLimiter(max_rate=PIPEDRIVE["bucket_capacity"],
                       time_period=2)  # e.g. 40 req per 2s

client = httpx.AsyncClient(
    base_url="https://api.pipedrive.com/v1",
    params={"api_token": PIPEDRIVE["api_token"]},
)

async def request(method, path, **kwargs):
    async with limiter:
        resp = await client.request(method, path, **kwargs)
        if resp.status_code == 429:
            reset = int(resp.headers.get("X-RateLimit-Reset", "1"))
            await asyncio.sleep(reset)
            return await request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

async def create_item(fields, entity_type):
    path = f"/{entity_type.lower()}s"
    return await request("POST", path, json=fields)

async def update_item(item_id, fields, entity_type):
    path = f"/{entity_type.lower()}s/{item_id}"
    return await request("PUT", path, json=fields)

async def get_item(item_id, entity_type):
    path = f"/{entity_type.lower()}s/{item_id}"
    return await request("GET", path)

async def get_custom_fields(entity_type):
    path = f"/{entity_type.lower()}s/fields"
    return await request("GET", path)

async def update_activity(activity_id, fields):
    path = f"/activities/{activity_id}"
    return await request("PATCH", path, json=fields)
