TITLE_FONT = ("Segoe UI", 22, "bold")
SUBTITLE_FONT = ("Segoe UI", 11)
CARD_TITLE_FONT = ("Segoe UI", 10, "bold")
CARD_VALUE_FONT = ("Segoe UI", 20, "bold")
BADGE_FONT = ("Segoe UI", 10, "bold")
LOG_FONT = ("Consolas", 10)


def role_bootstyle(is_admin: bool) -> str:
    return "inverse-danger" if is_admin else "inverse-secondary"


def status_bootstyle(device_status: str) -> str:
    status = (device_status or "").lower()
    if status == "free":
        return "success"
    if status == "busy":
        return "warning"
    if status == "error":
        return "danger"
    return "secondary"