"""
mcp-google-calendar-digest — Calendar digest for scheduled push.

Actions: Produces human-readable digest text for LINE push delivery.
Range: today, tomorrow, week, next_3days
Format: summary (concise) or detailed (with location & attendees)
"""

import json
import os
import sys
from datetime import datetime, timedelta


def _load_credentials():
    """Load Google credentials (Service Account or OAuth) from UMA-injected env."""
    cred_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
    cred_type = os.getenv("GOOGLE_CREDENTIAL_TYPE", "")

    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError("Google 帳號尚未綁定。請先完成 Google 授權。")

    if cred_type == "service_account" or "service_account" in cred_path:
        from google.oauth2 import service_account
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        return service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    with open(cred_path, "r", encoding="utf-8") as f:
        cred_data = json.load(f)

    creds = Credentials(
        token=cred_data.get("token"),
        refresh_token=cred_data.get("refresh_token"),
        token_uri=cred_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=cred_data.get("client_id"),
        client_secret=cred_data.get("client_secret"),
        scopes=cred_data.get("scopes", []),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        cred_data["token"] = creds.token
        with open(cred_path, "w", encoding="utf-8") as f:
            json.dump(cred_data, f, ensure_ascii=False, indent=2)

    return creds


def _get_service():
    from googleapiclient.discovery import build
    creds = _load_credentials()
    return build("calendar", "v3", credentials=creds)


WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def _get_time_range(range_type):
    now = datetime.now().astimezone()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range_type == "today":
        return today_start, today_start + timedelta(days=1), f"{now.month}/{now.day} {WEEKDAY_NAMES[now.weekday()]}"
    elif range_type == "tomorrow":
        tmr = today_start + timedelta(days=1)
        return tmr, tmr + timedelta(days=1), f"{tmr.month}/{tmr.day} {WEEKDAY_NAMES[tmr.weekday()]}"
    elif range_type == "week":
        # Monday to Friday of current week
        monday = today_start - timedelta(days=now.weekday())
        friday = monday + timedelta(days=5)
        return monday, friday, f"{monday.month}/{monday.day}-{friday.month}/{friday.day}"
    elif range_type == "next_3days":
        end = today_start + timedelta(days=3)
        return today_start, end, f"{now.month}/{now.day}-{end.month}/{end.day}"
    else:
        return today_start, today_start + timedelta(days=1), "今日"


def _format_time(dt_str):
    """Extract HH:MM from ISO datetime string."""
    try:
        from dateutil.parser import parse as dtparse
        dt = dtparse(dt_str)
        return dt.strftime("%H:%M")
    except Exception:
        return dt_str[:5] if len(dt_str) >= 5 else dt_str


def _extract_meet_link(event):
    conf = event.get("conferenceData")
    if not conf:
        return None
    for ep in conf.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri")
    return None


def _format_summary(events, label):
    if not events:
        return f"📅 {label}\n\n🟢 今天沒有行程，好好利用！"

    lines = [f"📅 {label}\n"]
    for e in events:
        start = _format_time(e.get("start", {}).get("dateTime", ""))
        end = _format_time(e.get("end", {}).get("dateTime", ""))
        title = e.get("summary", "(無標題)")
        location = e.get("location", "")
        loc_str = f"（{location}）" if location else ""
        meet = _extract_meet_link(e)
        meet_str = f"\n   📎 {meet}" if meet else ""
        lines.append(f"🔵 {start}-{end} {title}{loc_str}{meet_str}")

    lines.append(f"\n共 {len(events)} 個行程")
    return "\n".join(lines)


def _format_detailed(events, label):
    if not events:
        return f"📅 {label}\n\n🟢 沒有行程"

    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for e in events:
        dt_str = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
        try:
            from dateutil.parser import parse as dtparse
            dt = dtparse(dt_str)
            key = dt.strftime("%m/%d") + " " + WEEKDAY_NAMES[dt.weekday()]
        except Exception:
            key = "其他"
        by_date[key].append(e)

    lines = [f"📅 {label}\n"]
    for date_key, day_events in by_date.items():
        lines.append(f"【{date_key}】")
        if not day_events:
            lines.append("  全天無行程")
        for e in day_events:
            start = _format_time(e.get("start", {}).get("dateTime", ""))
            title = e.get("summary", "(無標題)")
            location = e.get("location", "")
            attendees = [a.get("email", "").split("@")[0] for a in e.get("attendees", [])]
            parts = [f"  {start} {title}"]
            if location:
                parts.append(f"@{location}")
            if attendees:
                parts.append(f"({', '.join(attendees[:5])})")
            meet = _extract_meet_link(e)
            if meet:
                parts.append(f"\n    📎 {meet}")
            lines.append(" ".join(parts))
        lines.append("")

    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        args = {}

    range_type = args.get("range", "today")
    fmt = args.get("format", "summary")

    try:
        service = _get_service()
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return

    try:
        start, end, label = _get_time_range(range_type)
        result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()

        events = result.get("items", [])

        if fmt == "detailed":
            digest = _format_detailed(events, label)
        else:
            digest = _format_summary(events, label)

        print(json.dumps({"status": "success", "digest": digest}, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
