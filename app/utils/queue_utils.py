from datetime import datetime
import uuid


def generate_request_id(prefix: str = "req") -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{now}_{uuid.uuid4().hex[:8]}"