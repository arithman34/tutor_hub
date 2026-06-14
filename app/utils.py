def cap_name(s: str) -> str:
    """Capitalize the first letter of a string and strip leading/trailing whitespace."""
    s = s.strip()
    return (s[0].upper() + s[1:]) if s else s
