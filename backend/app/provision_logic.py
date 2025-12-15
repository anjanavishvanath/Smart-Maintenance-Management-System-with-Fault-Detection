import uuid
import time
from db import insert_provisioning_token, get_user_by_email

SLPT_EXPIRY_SECONDS = 300 # 5 minutes

def generate_slpt(user_id: int, enrollment_id: str) -> dict:
    """Generates a SLPT and stores it in the DB linked to the user and MAC."""
    slpt_value = str(uuid.uuid4())
    expires_at = time.time()+SLPT_EXPIRY_SECONDS
    insert_provisioning_token(
        slpt_value=slpt_value,
        user_id=user_id,
        enrollment_id=enrollment_id, #mac address
        expires_at=expires_at
    )

    return {
        "slpt": slpt_value,
        "expires_at": expires_at
    }