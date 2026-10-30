"""Tools the agent can call. Each tool takes the Store plus keyword arguments
and returns JSON-serialisable data."""

from datetime import date as Date

from .slots import (
    SLOT_MINUTES,
    availability_from_busy,
    combine_availability,
    find_free_windows,
    slot_to_time,
    time_to_slot,
    time_to_slot_ceil,
    time_to_minutes,
)
from .store import Store


def validate_person(store: Store, person: str) -> None:
    known_ids = {entry["id"] for entry in store.people}
    if not isinstance(person, str) or person not in known_ids:
        raise ValueError(f"Unknown attendee: {person!r}")


def validate_date(store: Store, date: str) -> None:
    try:
        if not isinstance(date, str) or Date.fromisoformat(date).isoformat() != date:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Date must be a valid YYYY-MM-DD date") from None
    covered = [day for calendar in store.calendars.values() for day in calendar]
    if not covered or not min(covered) <= date <= max(covered):
        raise ValueError("Date is outside the sample calendar coverage")


def list_people(store: Store) -> list[dict]:
    """Return everyone in the directory."""
    return store.people


def get_busy_times(store: Store, person: str, date: str) -> list[dict]:
    """Return a person's busy blocks on a date (YYYY-MM-DD)."""
    validate_person(store, person)
    validate_date(store, date)
    return store.calendars.get(person, {}).get(date, [])


def find_free_slots(
    store: Store,
    attendees: list[str],
    date: str,
    duration_minutes: int,
    earliest: str | None = None,
    latest: str | None = None,
) -> list[dict]:
    """Find every time on `date` when all attendees are free for `duration_minutes`.

    `earliest` and `latest` optionally narrow the search to part of the day
    (e.g. earliest="12:00" for "afternoon").
    """
    if not isinstance(attendees, list) or not attendees:
        raise ValueError("attendees must be a non-empty list")
    for person in attendees:
        validate_person(store, person)
    validate_date(store, date)
    lower = time_to_minutes(earliest) if earliest is not None else 9 * 60
    upper = time_to_minutes(latest) if latest is not None else 17 * 60
    if lower >= upper:
        raise ValueError("earliest must be before latest")
    calendars = []
    for person in attendees:
        busy = store.calendars.get(person, {}).get(date, [])
        calendars.append(availability_from_busy(busy))

    if type(duration_minutes) is not int or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive integer")

    free = combine_availability(calendars)
    slots_needed = (duration_minutes + SLOT_MINUTES - 1) // SLOT_MINUTES
    start_slot = time_to_slot_ceil(earliest) if earliest is not None else 0
    end_slot = time_to_slot(latest) if latest is not None else None

    starts = find_free_windows(free, slots_needed, start_slot, end_slot)
    return [
        {"start": slot_to_time(s), "end": slot_to_time(s + slots_needed)}
        for s in starts
    ]


def find_free_slots_on_dates(
    store: Store, attendees: list[str], dates: list[str], duration_minutes: int,
    earliest: str | None = None, latest: str | None = None,
) -> list[dict]:
    """Return unique dated options, sorted chronologically, for all supplied dates."""
    if not isinstance(dates, list) or not dates:
        raise ValueError("dates must be a non-empty list")
    for date in dates:
        validate_date(store, date)
    return [
        {"date": date, **slot}
        for date in sorted(set(dates))
        for slot in find_free_slots(store, attendees, date, duration_minutes, earliest, latest)
    ]


TOOLS = {
    "list_people": list_people,
    "get_busy_times": get_busy_times,
    "find_free_slots": find_free_slots,
    "find_free_slots_on_dates": find_free_slots_on_dates,
}
