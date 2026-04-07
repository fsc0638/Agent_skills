"""
mcp-google-meet — Google Meet link creation skill.

Actions: create, instant, get_link
Uses Google Calendar API with conferenceData to generate Meet links.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta


def _load_credentials():
    """Load Google OAuth credentials for Meet (personal OAuth only, SA not supported)."""
    cred_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
    cred_type = os.getenv("GOOGLE_CREDENTIAL_TYPE", "")

    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError("Google 帳號尚未綁定。建立 Meet 連結需要綁定個人 Google 帳號。")

    # Service Account cannot create Meet links
    if cred_type == "service_account" or "service_account" in cred_path:
        raise RuntimeError(
            "Google Meet 連結無法透過 Service Account 建立。"
            "請先綁定你的個人 Google 帳號才能使用 Meet 功能。"
        )

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


def _extract_meet_link(event):
    """Extract Google Meet link from event conferenceData."""
    conf = event.get("conferenceData")
    if not conf:
        return None
    for ep in conf.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri")
    return None


def action_create(service, args):
    title = args.get("title", "線上會議")
    start = args.get("start")
    if not start:
        return {"status": "error", "message": "缺少 start 時間參數"}

    duration = args.get("duration_minutes", 60)
    from dateutil.parser import parse as dtparse
    s = dtparse(start)
    end = (s + timedelta(minutes=duration)).isoformat()

    body = {
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if args.get("attendees"):
        body["attendees"] = [{"email": e} for e in args["attendees"]]

    event = service.events().insert(
        calendarId="primary",
        body=body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    meet_link = _extract_meet_link(event)
    return {
        "status": "success",
        "meet_link": meet_link,
        "event_id": event.get("id"),
        "title": title,
        "start": start,
        "end": end,
        "html_link": event.get("htmlLink", ""),
    }


def action_instant(service, args):
    """Create an instant meeting starting now."""
    now = datetime.now().astimezone()
    duration = args.get("duration_minutes", 60)
    start = now.isoformat()
    end = (now + timedelta(minutes=duration)).isoformat()

    title = args.get("title", "即時會議")

    body = {
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if args.get("attendees"):
        body["attendees"] = [{"email": e} for e in args["attendees"]]

    event = service.events().insert(
        calendarId="primary",
        body=body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    meet_link = _extract_meet_link(event)
    return {
        "status": "success",
        "meet_link": meet_link,
        "event_id": event.get("id"),
        "start": start,
        "end": end,
    }


def action_get_link(service, args):
    event_id = args.get("event_id")
    if not event_id:
        return {"status": "error", "message": "缺少 event_id 參數"}

    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    meet_link = _extract_meet_link(event)
    if not meet_link:
        return {"status": "error", "message": "此事件沒有 Google Meet 連結"}

    return {
        "status": "success",
        "meet_link": meet_link,
        "title": event.get("summary", ""),
        "event_id": event_id,
    }


def main():
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        args = {}

    action = args.get("action", "instant")

    try:
        service = _get_service()
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return

    actions = {
        "create": action_create,
        "instant": action_instant,
        "get_link": action_get_link,
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
