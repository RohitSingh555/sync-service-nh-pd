# state.py
import aioredis
redis = aioredis.from_url("redis://localhost")

async def get_last_poll(): return await redis.get("last_nethunt_poll")
async def set_last_poll(ts): return await redis.set("last_nethunt_poll", ts)

async def map_pd_to_nh(pd_id, nh_id): return await redis.set(f"map:pd:{pd_id}", nh_id)
async def get_nh_by_pd(pd_id): return await redis.get(f"map:pd:{pd_id}")
# …and vice versa…
