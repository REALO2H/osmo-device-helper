from dataclasses import dataclass, field
from typing import List


@dataclass
class UserContext:
    username: str
    is_admin: bool = False
    is_operator: bool = True


@dataclass
class MeasurementResult:
    port: int
    lot_number: str
    value: str
    unit: str
    timestamp: str
    operator: str
    flags: str = ""
    error_or_comment: str = ""


@dataclass
class QueueState:
    device_status: str = "free"   # free / busy / error
    owner_user: str = ""
    reserved_ports: int = 0
    used_ports: int = 0
    remaining_ports: int = 0
    queue_locked: bool = False
    message: str = "Device is available"
    recent_results: List[MeasurementResult] = field(default_factory=list)