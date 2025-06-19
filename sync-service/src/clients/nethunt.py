import httpx
import base64

NETHUNT_TASKS_FOLDER_ID = "67e17578cc9bea52af34a271" 
class NetHuntClient:
    def __init__(self, email, api_key):
        credentials = f"{email}:{api_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(
            base_url="https://nethunt.com/api/v1",
            headers=self.headers
        )

    async def get_recent_records(self, folder_id, since, limit=None, field_names=None):
        params = {
            "since": since,
            "limit": limit,
        }
        if field_names:
            for field_name in field_names:
                params.setdefault("fieldName", []).append(field_name)

        resp = await self.client.get(f"/zapier/triggers/updated-record/{folder_id}", params=params)
        
        print(f"Response status code: {resp}")
        resp.raise_for_status()
        return resp.json()
    
    async def get_freshly_updated_task_records(self, since, limit=10):
        return await self.get_recent_records(
            folder_id=NETHUNT_TASKS_FOLDER_ID,
            since=since,
            limit=limit
        )
    
    async def get_freshly_created_records(self, folder_id, since, limit=10, field_names=None):
        params = {
            "since": since,
            "limit": limit,
        }
        if field_names:
            for field_name in field_names:
                params.setdefault("fieldName", []).append(field_name)

        resp = await self.client.get(f"/zapier/triggers/new-record/{folder_id}", params=params)
        
        print(f"Response status code: {resp}")
        resp.raise_for_status()
        return resp.json()

    async def update_record(self, record_id, fields):
        resp = await self.client.patch(f"/records/{record_id}", json=fields)
        if resp.status_code == 404:
            return None  # Handle missing record gracefully
        resp.raise_for_status()
        return resp.json()

    async def create_record(self, fields):
        resp = await self.client.post("/records", json=fields)
        resp.raise_for_status()
        return resp.json()["data"]

    async def get_writable_folders(self):
        resp = await self.client.get("/zapier/triggers/readable-folder")
        resp.raise_for_status()
        return resp.json()

    async def get_folder_fields(self, folder_id):
        resp = await self.client.get(f"/zapier/triggers/folder-field/{folder_id}")
        resp.raise_for_status()
        return resp.json()

# Replace with your email and API key
nethunt_client = NetHuntClient(email="agilemorphsolutions@gmail.com", api_key="30741f0a-d62d-4703-b0d4-0a03fe6f8782")
