# Assignment notes

## Part A: findings and fixes

- Boundary reproduction: the last valid start and exact-fit windows were omitted.
  The user applied the inclusive endpoint fix and regression tests with Codex
  guidance. The existing afternoon expectation now includes 16:30-17:00 because
  both attendees are free then.
- Duration reproduction: 45 minutes became 30; zero and negative durations made
  invalid windows. The user added validation and ceiling division with guidance.
  Retained that behavior and reused SLOT_MINUTES instead of magic numbers.
- Added strict clock parsing, inward rounding of search bounds, and clipping
  indices to working hours. Reject reversed bounds and malformed busy intervals.
  Reject unequal availability lengths rather than silently truncating them.
- Unknown IDs previously looked like empty calendars. Validate attendees and
  non-empty lists in tools, including get_busy_times. Validate ISO dates and
  sample coverage. Known people with missing events within coverage are free.
- Agent actions now require an object with exactly a final string or a tool name
  and argument object. Invalid output, unknown tools, bad arguments and model
  exceptions yield deliberate messages. Fail fast rather than retrying invalid
  requests. Repeated calls stop at a configurable limit (default 12).
- Verified options are rendered in code so final prose cannot invent meetings.
  Two original agent tests changed: unverified final text now yields clarification;
  a successful search yields all verified options rather than a scripted sentence.
- The optional adapter now has a 30-second network timeout. The CLI identifies
  its fixed demo rather than implying that it interpreted a custom request.

## Part B: flexible dates

- Added find_free_slots_on_dates, exposed in the tool registry and prompt. It
  reuses single-day validation/search, validates every date before returning,
  deduplicates dates, and returns dated options in chronological order.
- This helps employees flexible about the day and stays within the sample data.
  Chosen over UI or booking because it adds user value with a small, testable change.

## AI usage

- Codex reviewed the starter and explained the first fixes step by step. The user
  applied the boundary and duration fixes/tests.
- A specific corrected AI suggestion: the initial duration snippet hard-coded
  `(duration_minutes + 29) // 30`. The implementation replaced those numbers with
  SLOT_MINUTES so scheduling arithmetic has one source of truth.
