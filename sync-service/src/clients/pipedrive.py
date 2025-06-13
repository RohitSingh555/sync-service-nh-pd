# clients/pipedrive.py
import httpx, asyncio
from aiolimiter import AsyncLimiter

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
