# src/sync_engine.py

FIELD_MAP = {
    "Deal": {
        "title": "name",
        "due_date": "due_date",
        "owner_id": "assignee_id",
        "person_id": "person_id",
        "org_id": "org_id",
        "description": "description",
    },
    "Task": {
        "subject": "title",
        "due_date": "due_date",
        "assigned_to_user_id": "owner_id",
        "content": "description",
    }
}


async def handle_pd_webhook(body: dict):
    current = body.get("current", {})
    previous = body.get("previous", {})
    entity_type = "Deal" if "title" in current else "Task"

    pd_id = str(current.get("id"))
    nh_id = await get_nh_by_pd(pd_id)  # Lookup Redis mapping

    # Detect only changed fields
    updated_fields = {}
    for pd_field, nh_field in FIELD_MAP[entity_type].items():
        if current.get(pd_field) != previous.get(pd_field):
            updated_fields[nh_field] = current.get(pd_field)

    # If no changes, skip
    if not updated_fields:
        return

    if nh_id:
        # Update existing NetHunt record
        await nethunt_client.update_record(nh_id, updated_fields)
    else:
        # Create fallback: search by title
        name = current.get("title") or current.get("subject")
        matched = await nethunt_client.search_record_by_name(name)

        if matched:
            nh_id = matched["id"]
            await nethunt_client.update_record(nh_id, updated_fields)
        else:
            # Create new NetHunt record
            payload = {
                "name": current.get("title") or current.get("subject"),
                **updated_fields
            }
            nh_id = await nethunt_client.create_record(payload)

        # Store cross-ID
        await map_pd_to_nh(pd_id, nh_id)
        await map_nh_to_pd(nh_id, pd_id)


async def sync_nethunt_records(records: list[dict]):
    for rec in records:
        nh_id = str(rec["id"])
        pd_id = await get_pd_by_nh(nh_id)
        entity_type = "Deal" if "title" in rec else "Task"

        mapped_fields = {
            pd_key: rec.get(nh_key)
            for pd_key, nh_key in FIELD_MAP[entity_type].items()
            if rec.get(nh_key) is not None
        }

        if pd_id:
            await pipedrive_client.update_item(pd_id, mapped_fields, entity_type)
        else:
            created = await pipedrive_client.create_item(mapped_fields, entity_type)
            pd_id = str(created["id"])

        await map_nh_to_pd(nh_id, pd_id)
        await map_pd_to_nh(pd_id, nh_id)
