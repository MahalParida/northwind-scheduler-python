import json

import pytest

from scheduler.agent import SchedulingAgent
from scheduler.model import FakeModel, final, tool_call
from scheduler.slots import availability_from_busy, combine_availability, find_free_windows, time_to_minutes
from scheduler.store import Store
from scheduler.tools import find_free_slots, find_free_slots_on_dates, get_busy_times


def search(**overrides):
    args = dict(attendees=["priya", "sam"], date="2026-11-03", duration_minutes=30)
    return find_free_slots(Store.load(), **(args | overrides))


@pytest.mark.parametrize("overrides", [
    {"attendees": []}, {"attendees": "sam"}, {"attendees": [None]},
    {"attendees": ["sam", "unknown"]}, {"date": "bad"}, {"date": None},
    {"date": "2026-02-30"}, {"date": "2026-11-05"}, {"date": "20261103"},
    {"earliest": "13:60"}, {"earliest": "9:00"}, {"earliest": ""},
    {"earliest": 12}, {"latest": "24:00"},
    {"earliest": "14:00", "latest": "13:00"},
    {"earliest": "14:00", "latest": "14:00"},
])
def test_invalid_search_arguments(overrides):
    with pytest.raises(ValueError):
        search(**overrides)


def test_unknown_person_is_not_an_empty_calendar():
    store = Store.load()
    with pytest.raises(ValueError, match="Unknown attendee"):
        get_busy_times(store, "unknown", "2026-11-03")
    assert get_busy_times(store, "dana", "2026-11-04") == []
    with pytest.raises(ValueError, match="Date"):
        get_busy_times(store, "sam", "bad")


def test_bounds_round_inward_and_stay_inside_workday():
    assert search(earliest="13:15", latest="14:15") == [{"start": "13:30", "end": "14:00"}]
    assert search(earliest="00:00", latest="23:59") == search()
    assert search(earliest="07:00", latest="08:00") == []
    assert search(earliest="18:00", latest="19:00") == []
    assert search(earliest="16:30") == [{"start": "16:30", "end": "17:00"}]


def test_window_search_matches_exhaustive_oracle():
    for mask in range(64):
        free = [bool(mask & (1 << i)) for i in range(6)]
        for duration in range(1, 8):
            for lower, upper in [(-2, 9), (0, 6), (1, 5), (3, 3)]:
                expected = [
                    start for start in range(6)
                    if start >= lower and start + duration <= min(6, upper)
                    and all(free[i] for i in range(start, start + duration))
                ]
                assert find_free_windows(free, duration, lower, upper) == expected
    assert find_free_windows([True] * 16, 16) == [0]


@pytest.mark.parametrize("duration", [0, -1, True, 1.5])
def test_invalid_slot_counts(duration):
    with pytest.raises(ValueError):
        find_free_windows([True] * 16, duration)


def test_calendar_validation_and_partial_overlap():
    with pytest.raises(ValueError):
        combine_availability([[True], [True, False]])
    with pytest.raises(ValueError):
        availability_from_busy([{"start": "11:00", "end": "10:00"}])
    assert availability_from_busy([{"start": "08:00", "end": "18:00"}]) == [False] * 16
    assert availability_from_busy([{"start": "17:00", "end": "18:00"}]) == [True] * 16
    free = availability_from_busy([{"start": "09:15", "end": "09:45"}])
    assert free[:3] == [False, False, True]


def test_all_returned_options_are_long_enough_and_conflict_free():
    store = Store.load()
    for duration in [15, 30, 45, 60, 480, 481]:
        for slot in search(duration_minutes=duration):
            start, end = map(time_to_minutes, (slot["start"], slot["end"]))
            assert end - start == ((duration + 29) // 30) * 30
            for person in ["priya", "sam"]:
                for busy in get_busy_times(store, person, "2026-11-03"):
                    assert end <= time_to_minutes(busy["start"]) or start >= time_to_minutes(busy["end"])


def test_multidate_matches_sorted_unique_single_day_results():
    store = Store.load()
    dates = ["2026-11-04", "2026-11-02", "2026-11-03", "2026-11-02"]
    actual = find_free_slots_on_dates(store, ["priya", "sam"], dates, 45, "13:15", "17:00")
    expected = [
        {"date": date, **slot} for date in sorted(set(dates))
        for slot in find_free_slots(store, ["priya", "sam"], date, 45, "13:15", "17:00")
    ]
    assert actual == expected and actual
    assert find_free_slots_on_dates(store, ["sam"], dates, 600) == []


@pytest.mark.parametrize("dates", [[], "2026-11-03", [None], ["2026-11-03", "bad"], ["2026-11-05"]])
def test_multidate_rejects_invalid_dates(dates):
    with pytest.raises(ValueError):
        find_free_slots_on_dates(Store.load(), ["sam"], dates, 30)


@pytest.mark.parametrize("raw", [
    "not json", "null", "[]", "{}", '{"final":42}', '{"final":""}',
    '{"final":"ok","tool":"list_people","args":{}}',
    '{"tool":[],"args":{}}', '{"tool":"list_people","args":[]}',
    '{"tool":"missing","args":{}}', '{"tool":"find_free_slots","args":{}}',
    '{"tool":"list_people","args":{"unexpected":true}}',
])
def test_bad_model_output_fails_gracefully(raw):
    model = FakeModel([raw, final("This must not be returned")])
    answer = SchedulingAgent(model, Store.load()).run("Find a meeting")
    assert isinstance(answer, str) and answer
    assert "This must not" not in answer
    assert len(model.calls) == 1


def test_repeating_model_is_stopped():
    model = FakeModel([tool_call("list_people")], loop_last=True)
    answer = SchedulingAgent(model, Store.load(), max_steps=3).run("hi")
    assert "step limit" in answer
    assert len(model.calls) == 3


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_step_limit(limit):
    with pytest.raises(ValueError):
        SchedulingAgent(FakeModel([]), Store.load(), max_steps=limit)


def test_model_failure_is_reported():
    assert "couldn't reach" in SchedulingAgent(FakeModel([]), Store.load()).run("hi")


def test_unknown_attendee_failure_cannot_be_overridden():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["sam", "unknown"], date="2026-11-03", duration_minutes=30),
        final("Everyone is free"),
    ])
    answer = SchedulingAgent(model, Store.load()).run("Find time with Sam and unknown")
    assert "Unknown attendee" in answer
    assert len(model.calls) == 1


def test_multidate_agent_uses_verified_options_not_fabricated_final():
    model = FakeModel([
        tool_call("find_free_slots_on_dates", attendees=["sam"], dates=["2026-11-04", "2026-11-03"],
                  duration_minutes=30, earliest="16:30"),
        final("Imaginary Person is free at 03:00"),
    ])
    answer = SchedulingAgent(model, Store.load()).run("Find late slots for Sam")
    assert "Imaginary" not in answer and "03:00" not in answer
    assert answer.index("2026-11-03") < answer.index("2026-11-04")
    assert "Sam Okafor" in answer
    assert len(json.loads(model.calls[1][-1]["content"])) == 2


def test_no_matches_cannot_be_overridden():
    model = FakeModel([
        tool_call("find_free_slots", attendees=["sam"], date="2026-11-03", duration_minutes=600),
        final("09:00 works"),
    ])
    assert "No matching times" in SchedulingAgent(model, Store.load()).run("Find a long meeting")


def test_final_without_search_cannot_invent_meeting():
    answer = SchedulingAgent(FakeModel([final("Unknown is free at 03:00")]), Store.load()).run("Find time")
    assert "haven't verified" in answer and "03:00" not in answer
