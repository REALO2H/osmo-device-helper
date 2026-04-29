APP_TITLE = "OSMO Device Helper"

# ttkbootstrap theme
THEME_NAME = "superhero"  

# GUI / worker timing
REFRESH_INTERVAL_MS = 200
WORKER_POLL_INTERVAL_SEC = 1.0

# Hard cap for queue reservation
MAX_PORTS = 24

# Visual layout
PORT_GRID_COLUMNS = 8   # 24 ports -> 3 rows x 8 columns

# Simple admin list for testing
ADMIN_USERS = {
    "administrator",
    "admin",
    "labadmin",
}

# Demo / mock user
MOCK_OTHER_USER = "other.operator"