import getpass
from app.config.settings import ADMIN_USERS
from app.models.state import UserContext


class AuthService:
    @staticmethod
    def get_current_user() -> str:
        try:
            return getpass.getuser()
        except Exception:
            return "unknown"

    @staticmethod
    def get_user_context() -> UserContext:
        username = AuthService.get_current_user()
        is_admin = username.strip().lower() in ADMIN_USERS
        return UserContext(
            username=username,
            is_admin=is_admin,
            is_operator=True
        )