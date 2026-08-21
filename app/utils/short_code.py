import secrets
import string

BASE62_ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length: int = 6) -> str:
    """
    Generate a random URL-safe short code.
    """
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))
