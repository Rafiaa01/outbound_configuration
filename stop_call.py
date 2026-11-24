import argparse
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

load_dotenv()
client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

LIVE = ("queued", "ringing", "in-progress")
FINISHED = ("completed", "failed", "busy", "no-answer", "canceled")
PKT = timezone(timedelta(hours=5))  # Pakistan time, for readable timestamps


def fmt_time(dt):
    return dt.astimezone(PKT).strftime("%d %b %H:%M:%S") if dt else "-"


def print_table(title, calls, numbered=False):
    print(f"\n{title} ({len(calls)})")
    if not calls:
        print("  none")
        return
    print(f"  {'#' if numbered else ' '}  {'Call SID':<36} {'To':<15} {'Status':<12} {'Started (PKT)':<17} Duration")
    for i, c in enumerate(calls, 1):
        num = str(i) if numbered else " "
        dur = f"{c.duration}s" if c.duration else "-"
        print(f"  {num}  {c.sid:<36} {c.to:<15} {c.status:<12} {fmt_time(c.start_time or c.date_created):<17} {dur}")


def hang_up(call):
    # A connected call is ended with "completed"; one not answered yet is "canceled".
    new_status = "completed" if call.status == "in-progress" else "canceled"
    try:
        updated = client.calls(call.sid).update(status=new_status)
        print(f"  stopped {call.sid} ({call.to}): {call.status} -> {updated.status}")
    except TwilioRestException as e:
        print(f"  could not stop {call.sid}: {e.msg} (code {e.code})")


def choose(live):
    """Ask which live calls to stop. Returns the chosen calls."""
    answer = input("\nStop which calls? Enter numbers (e.g. 1,3), 'all', or press Enter to cancel: ")
    answer = answer.strip().lower()
    if not answer:
        return []
    if answer == "all":
        return live
    chosen = []
    for part in answer.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(live):
            chosen.append(live[int(part) - 1])
        else:
            print(f"  ignoring '{part}' (not a number from the list)")
    return chosen


def single_call(sid):
    try:
        call = client.calls(sid).fetch()
    except TwilioRestException as e:
        print(f"Could not find call {sid}: {e.msg}")
        return
    print_table("Call details", [call])
    if call.status not in LIVE:
        print(f"\nThis call already ended with status '{call.status}'. Nothing to stop.")
        return
    if input("\nStop this call? [y/N] ").strip().lower() == "y":
        hang_up(call)
    else:
        print("Nothing changed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("call_sid", nargs="?", help="check (and optionally stop) one call")
    parser.add_argument("--hours", type=int, default=24, help="how far back the report goes")
    args = parser.parse_args()

    if args.call_sid:
        single_call(args.call_sid)
        return

    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)  # noqa: UP017
    print(f"Checking calls since {fmt_time(since)} PKT ...")

    # Step 1: status report
    live = []
    for status in LIVE:
        live += client.calls.list(status=status, limit=50)
    recent = client.calls.list(start_time_after=since, limit=100)
    finished = [c for c in recent if c.status in FINISHED]

    counts = {}
    for c in live + finished:
        counts[c.status] = counts.get(c.status, 0) + 1
    print("\nSummary: " + (", ".join(f"{s}={n}" for s, n in sorted(counts.items())) or "no calls"))

    print_table("FINISHED calls (already ended, nothing to stop)", finished)
    print_table("LIVE calls (still queued, ringing or connected)", live, numbered=True)

    # Step 2: stop only what you choose
    if not live:
        print("\nNo live calls. If the server is still printing audio chunks, restart uvicorn.")
        return

    chosen = choose(live)
    if not chosen:
        print("Nothing changed.")
        return
    print()
    for c in chosen:
        hang_up(c)

    # Step 3: confirm
    still_live = [c for status in LIVE for c in client.calls.list(status=status, limit=50)]
    print_table("LIVE calls after stopping", still_live)


if __name__ == "__main__":
    main()
