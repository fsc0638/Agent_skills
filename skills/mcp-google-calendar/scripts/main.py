"""
mcp-google-calendar — Google Calendar management skill.

Actions: list, today, get, create, update, delete, free_busy
Reads Google OAuth credentials from GOOGLE_CREDENTIALS_PATH env var.
"""

import json
import os
import sys
from datetime import datetime, timedelta


def _load_credentials():
    """Load Google credentials from the path provided by UMA.
    Supports both Service Account (JSON key) and OAuth (user token).
    """
    cred_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
    cred_type = os.getenv("GOOGLE_CREDENTIAL_TYPE", "")

    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError(
            "Google 帳號尚未綁定。請先透過 LINE 或 Web UI 完成 Google OAuth 授權。"
        )

    # Service Account
    if cred_type == "service_account" or "service_account" in cred_path:
        from google.oauth2 import service_account
        SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"]
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)
        return creds

    # OAuth (personal user token)
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


def _now_iso():
    return datetime.now().astimezone().isoformat()


def _today_range():
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _format_event(event):
    start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
    end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date", "")
    # Google API: all-day event end date is exclusive (e.g. 4/30 means ends on 4/29)
    # Subtract 1 day for human-friendly display
    if "date" in event.get("end", {}) and not event.get("end", {}).get("dateTime"):
        from datetime import date as _date
        try:
            _end_date = _date.fromisoformat(end)
            end = (_end_date - timedelta(days=1)).isoformat()
        except (ValueError, TypeError):
            pass
    meet_link = None
    conf = event.get("conferenceData")
    if conf:
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri")
                break
    return {
        "event_id": event.get("id", ""),
        "title": event.get("summary", "(無標題)"),
        "start": start,
        "end": end,
        "location": event.get("location", ""),
        "description": event.get("description", ""),
        "meet_link": meet_link,
        "attendees": [a.get("email", "") for a in event.get("attendees", [])],
        "html_link": event.get("htmlLink", ""),
    }


def action_today(service, args):
    start, end = _today_range()
    result = service.events().list(
        calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy="startTime",
        maxResults=args.get("max_results", 20),
    ).execute()
    events = [_format_event(e) for e in result.get("items", [])]
    return {"status": "success", "events": events, "count": len(events)}


def action_list(service, args):
    start = args.get("start") or args.get("timeMin") or args.get("date_start") or _now_iso()
    end = args.get("end") or args.get("timeMax") or args.get("date_end")
    kwargs = {
        "calendarId": os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        "timeMin": start,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": args.get("max_results", 10),
    }
    if end:
        kwargs["timeMax"] = end
    result = service.events().list(**kwargs).execute()
    events = [_format_event(e) for e in result.get("items", [])]
    return {"status": "success", "events": events, "count": len(events)}


def action_get(service, args):
    event_id = args.get("event_id")
    if not event_id:
        return {"status": "error", "message": "缺少 event_id 參數"}
    event = service.events().get(calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), eventId=event_id).execute()
    return {"status": "success", "event": _format_event(event)}


def action_create(service, args):
    title = args.get("title", "新事件")
    start = args.get("start")
    if not start:
        return {"status": "error", "message": "缺少 start 時間參數"}

    end = args.get("end")
    if not end:
        # Default: +1 hour
        from dateutil.parser import parse as dtparse
        s = dtparse(start)
        end = (s + timedelta(hours=1)).isoformat()

    body = {
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if args.get("location"):
        body["location"] = args["location"]
    if args.get("description"):
        body["description"] = args["description"]
    if args.get("attendees"):
        body["attendees"] = [{"email": e} for e in args["attendees"]]

    event = service.events().insert(calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), body=body, sendUpdates="all").execute()
    return {
        "status": "success",
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink", ""),
    }


def action_update(service, args):
    event_id = args.get("event_id")
    if not event_id:
        return {"status": "error", "message": "缺少 event_id 參數"}

    event = service.events().get(calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), eventId=event_id).execute()

    if args.get("title"):
        event["summary"] = args["title"]
    if args.get("start"):
        event["start"] = {"dateTime": args["start"]}
    if args.get("end"):
        event["end"] = {"dateTime": args["end"]}
    if args.get("location"):
        event["location"] = args["location"]
    if args.get("description"):
        event["description"] = args["description"]
    if args.get("attendees"):
        event["attendees"] = [{"email": e} for e in args["attendees"]]

    updated = service.events().update(
        calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), eventId=event_id, body=event, sendUpdates="all"
    ).execute()
    return {
        "status": "success",
        "event_id": updated.get("id"),
        "html_link": updated.get("htmlLink", ""),
    }


def action_delete(service, args):
    event_id = args.get("event_id")
    if not event_id:
        return {"status": "error", "message": "缺少 event_id 參數"}
    service.events().delete(calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), eventId=event_id, sendUpdates="all").execute()
    return {"status": "success", "message": f"事件 {event_id} 已刪除"}


def action_free_busy(service, args):
    start = args.get("start")
    end = args.get("end")
    if not start or not end:
        return {"status": "error", "message": "free_busy 需要 start 和 end 參數"}

    _cal_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    body = {
        "timeMin": start,
        "timeMax": end,
        "items": [{"id": _cal_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get(_cal_id, {}).get("busy", [])
    return {"status": "success", "busy": busy}


def main():
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        args = {}

    action = args.get("action", "")
    # Auto-detect action from parameters when not explicitly set
    if not action:
        if any(k in args for k in ("start", "end", "timeMin", "timeMax", "date_start", "date_end")):
            action = "list"
        elif args.get("event_id"):
            action = "get"
        else:
            action = "today"

    try:
        service = _get_service()
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return

    actions = {
        "today": action_today,
        "list": action_list,
        "get": action_get,
        "create": action_create,
        "update": action_update,
        "delete": action_delete,
        "free_busy": action_free_busy,
    }

    handler = actions.get(action)
    if not handler:
        print(json.dumps({"status": "error", "message": f"未知操作: {action}"}, ensure_ascii=False))
        return

    try:
        result = handler(service, args)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
