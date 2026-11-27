"""Small tools that do not depend on AIVA's transport."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def current_time(timezone: str = "UTC") -> dict[str, str]:
    """Return the current time for an IANA time zone."""
    if not isinstance(timezone, str) or not timezone or len(timezone) > 100:
        raise ValueError("timezone must be a nonempty IANA time zone")
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("unknown IANA time zone") from exc
    return {"timezone": timezone, "datetime": now.isoformat()}
