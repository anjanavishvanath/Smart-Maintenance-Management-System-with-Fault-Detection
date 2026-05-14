import secrets
from datetime import datetime, timezone, timedelta
from db import insert_provisioning_token

SLPT_EXPIRY_SECONDS = 1800 # 30 minutes
SLPT_BYTES = 4  # 4 bytes -> 8 hex chars; ~32 bits of entropy, fine given MAC binding + 30-min expiry + single-use

def generate_slpt(user_id: int, enrollment_id: str) -> dict:
    """Generates a SLPT and stores it in the DB linked to the user and MAC."""
    # 8-char hex token (e.g. "a3f29b1c"). Short enough for a human to type during
    # device provisioning. Replaced uuid4() (36 chars) for usability.
    slpt_value = secrets.token_hex(SLPT_BYTES)
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