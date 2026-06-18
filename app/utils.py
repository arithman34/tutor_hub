import secrets
import string


def cap_name(s: str) -> str:
    """Capitalize the first letter of a string and strip leading/trailing whitespace."""
    s = s.strip()
    return (s[0].upper() + s[1:]) if s else s


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
