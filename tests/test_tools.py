from scheduler.store import Store
from scheduler.tools import find_free_slots, get_busy_times
import pytest

def test_get_busy_times():
    store = Store.load()
    busy = get_busy_times(store, "sam", "2026-11-04")
    assert busy == [{"start": "09:00", "end": "09:30", "title": "Standup"}]


def test_find_free_slots_for_two_people_in_the_afternoon():
    store = Store.load()
    slots = find_free_slots(
        store,
        attendees=["priya", "sam"],
        date="2026-11-03",
        duration_minutes=30,
        earliest="13:00",
    )
    assert slots == [
        {"start": "13:00", "end": "13:30"},
        {"start": "13:30", "end": "14:00"},
        {"start": "15:00", "end": "15:30"},
        {"start": "16:00", "end": "16:30"},
        {"start": "16:30", "end": "17:00"}
    ]


def test_find_free_slots_hour_long_meeting():
    store = Store.load()
    slots = find_free_slots(
        store, attendees=["priya", "sam"], date="2026-11-03", duration_minutes=60
    )
    assert {"start": "13:00", "end": "14:00"} in slots


def test_45_minutes_reserves_two_slots():
    slots = find_free_slots(
        Store.load(),
        attendees=["priya", "sam"],
        date="2026-11-03",
        duration_minutes=45,
        earliest="13:00",
        latest="14:00",
    )

    assert slots == [{"start": "13:00", "end": "14:00"}]


@pytest.mark.parametrize("duration", [0, -30, 30.5, "30", True, None])
def test_invalid_duration_is_rejected(duration):
    with pytest.raises(ValueError, match="positive integer"):
        find_free_slots(
            Store.load(),
            attendees=["priya", "sam"],
            date="2026-11-03",
            duration_minutes=duration,
        )
