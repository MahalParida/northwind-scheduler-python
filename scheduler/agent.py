"""The scheduling agent: a simple tool-calling loop."""

import json

from .model import Model
from .prompts import build_system_prompt
from .store import Store
from .tools import TOOLS


def _render_options(store: Store, args: dict, options: list[dict]) -> str:
    """Render only validated search data, never model-authored meeting claims."""
    names = {person["id"]: person["name"] for person in store.people}
    attendees = ", ".join(names[p] for p in dict.fromkeys(args["attendees"]))
    if not options:
        return f"No matching times for {attendees} within the requested dates and bounds."
    lines = [f"Available for {attendees}:"]
    lines.extend(
        f"{option.get('date', args.get('date'))} {option['start']}-{option['end']}"
        for option in options
    )
    lines.append("Durations are rounded up to 30-minute increments.")
    return "\n".join(lines)


class SchedulingAgent:
    def __init__(self, model: Model, store: Store, today: str = "2026-11-02", max_steps: int = 12):
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.model = model
        self.store = store
        self.today = today
        self.max_steps = max_steps

    def run(self, user_request: str) -> str:
        """Handle one user request and return the assistant's final answer."""
        messages = [
            {"role": "system", "content": build_system_prompt(self.store.people, self.today)},
            {"role": "user", "content": user_request},
        ]

        verified_answer = None
        for _ in range(self.max_steps):
            try:
                raw = self.model.complete(messages)
            except Exception:
                return "I couldn't reach the model. Please try again."
            try:
                if not isinstance(raw, str):
                    raise ValueError
                action = json.loads(raw)
                if not isinstance(action, dict):
                    raise ValueError
                if set(action) == {"final"}:
                    if not isinstance(action["final"], str) or not action["final"].strip():
                        raise ValueError
                    return verified_answer or (
                        "I haven't verified any meeting options. Please specify attendees, "
                        "a date or list of dates, and a duration."
                    )
                if set(action) != {"tool", "args"}:
                    raise ValueError
                if not isinstance(action["tool"], str) or not isinstance(action["args"], dict):
                    raise ValueError
            except (ValueError, TypeError, RecursionError):
                return "I couldn't understand the model's response. Please try again."
            messages.append({"role": "assistant", "content": raw})
            tool = TOOLS.get(action["tool"])
            if tool is None:
                return "The model requested an unsupported tool. Please try again."
            try:
                result = tool(self.store, **action["args"])
            except ValueError as exc:
                return f"I couldn't complete the request: {exc}"
            except TypeError:
                return "The model supplied invalid tool arguments. Please try again."
            except Exception:
                return "I couldn't read the calendar data. Please try again."
            if action["tool"] in {"find_free_slots", "find_free_slots_on_dates"}:
                verified_answer = _render_options(self.store, action["args"], result)
            messages.append({"role": "tool", "content": json.dumps(result)})
        return "I couldn't finish within the request's step limit. Please try a simpler request."
