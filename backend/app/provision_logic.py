import uuid
from datetime import datetime, timezone, timedelta
from db import insert_provisioning_token

SLPT_EXPIRY_SECONDS = 1800 # 30 minutes

def generate_slpt(user_id: int, enrollment_id: str) -> dict:
    """Generates a SLPT and stores it in the DB linked to the user and MAC."""
    slpt_value = str(uuid.uuid4())
    expires_datetime = datetime.now(timezone.utc) + timedelta(seconds=SLPT_EXPIRY_SECONDS)
    expires_timestamp_unix = int(expires_datetime.timestamp()) #calculating unix timestamp (seconds since epoc) for js to understand
    insert_provisioning_token(
        slpt_value=slpt_value,
        user_id=user_id,
        enrollment_id=enrollment_id, #mac address
        expires_at=expires_datetime
    )

    return {
        "slpt": slpt_value,
        "expires_timestamp_unix": expires_timestamp_unix,
        "expires_in_seconds": SLPT_EXPIRY_SECONDS
    }