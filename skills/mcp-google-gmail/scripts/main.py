"""
mcp-google-gmail — Gmail management skill.

Actions: list, search, read, send, reply, draft
Reads Google OAuth credentials from GOOGLE_CREDENTIALS_PATH env var.
"""

import base64
import json
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _load_credentials():
    """Load Google OAuth credentials from the path provided by UMA."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    cred_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError(
            "Google 帳號尚未綁定。請先透過 LINE 或 Web UI 完成 Google OAuth 授權。"
        )

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
    return build("gmail", "v1", credentials=creds)


def _parse_headers(headers):
    """Extract common headers from Gmail message headers list."""
    result = {}
    for h in headers:
        name = h.get("name", "").lower()
        if name in ("from", "to", "subject", "date", "cc"):
            result[name] = h.get("value", "")
    return result


def _get_body_text(payload):
    """Recursively extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    parts = payload.get("parts", [])
    for part in parts:
        text = _get_body_text(part)
        if text:
            return text
    return ""


def _get_attachments_info(payload):
    """Extract attachment filenames and sizes."""
    attachments = []
    for part in payload.get("parts", []):
        filename = part.get("filename")
        if filename:
            size = part.get("body", {}).get("size", 0)
            attachments.append({
                "filename": filename,
                "size": f"{size / 1024:.1f}KB" if size < 1048576 else f"{size / 1048576:.1f}MB",
            })
    return attachments


def action_list(service, args):
    max_results = args.get("max_results", 10)
    result = service.users().messages().list(
        userId="me", maxResults=max_results, labelIds=["INBOX"]
    ).execute()

    messages = []
    for msg_meta in result.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=msg_meta["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = _parse_headers(msg.get("payload", {}).get("headers", []))
        messages.append({
            "message_id": msg["id"],
            "from": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "snippet": msg.get("snippet", ""),
            "date": headers.get("date", ""),
            "unread": "UNREAD" in msg.get("labelIds", []),
        })

    return {"status": "success", "emails": messages, "count": len(messages)}


def action_search(service, args):
    query = args.get("query", "")
    max_results = args.get("max_results", 10)
    if not query:
        return {"status": "error", "message": "缺少 query 搜尋條件"}

    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = []
    for msg_meta in result.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=msg_meta["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = _parse_headers(msg.get("payload", {}).get("headers", []))
        messages.append({
            "message_id": msg["id"],
            "from": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "snippet": msg.get("snippet", ""),
            "date": headers.get("date", ""),
            "unread": "UNREAD" in msg.get("labelIds", []),
        })

    return {"status": "success", "emails": messages, "count": len(messages)}


def action_read(service, args):
    message_id = args.get("message_id")
    if not message_id:
        return {"status": "error", "message": "缺少 message_id 參數"}

    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = _parse_headers(payload.get("headers", []))
    body = _get_body_text(payload)
    attachments = _get_attachments_info(payload)

    return {
        "status": "success",
        "message_id": message_id,
        "from": headers.get("from", ""),
        "to": headers.get("to", "").split(","),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "body": body[:5000],  # Cap body to prevent token overflow
        "attachments": attachments,
    }


def action_send(service, args):
    to_list = args.get("to", [])
    if not to_list:
        return {"status": "error", "message": "缺少 to 收件人"}

    subject = args.get("subject", "(無主旨)")
    body = args.get("body", "")
    body_format = args.get("body_format", "plain")
    cc = args.get("cc", [])

    msg = MIMEMultipart() if body_format == "html" else MIMEText(body, "plain", "utf-8")
    if body_format == "html":
        msg.attach(MIMEText(body, "html", "utf-8"))

    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return {
        "status": "success",
        "message_id": result.get("id", ""),
        "thread_id": result.get("threadId", ""),
    }


def action_reply(service, args):
    message_id = args.get("message_id")
    if not message_id:
        return {"status": "error", "message": "缺少 message_id 參數"}

    body_text = args.get("body", "")
    body_format = args.get("body_format", "plain")
    cc = args.get("cc", [])

    # Get original message for threading
    original = service.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID"]
    ).execute()
    orig_headers = _parse_headers(original.get("payload", {}).get("headers", []))
    thread_id = original.get("threadId", "")

    # Get Message-ID header for In-Reply-To
    message_id_header = ""
    for h in original.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == "message-id":
            message_id_header = h.get("value", "")
            break

    reply_to = orig_headers.get("from", "")
    subject = orig_headers.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    msg = MIMEText(body_text, body_format, "utf-8")
    msg["To"] = reply_to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if message_id_header:
        msg["In-Reply-To"] = message_id_header
        msg["References"] = message_id_header

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = service.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()

    return {
        "status": "success",
        "message_id": result.get("id", ""),
        "thread_id": result.get("threadId", ""),
    }


def action_draft(service, args):
    subject = args.get("subject", "(無主旨)")
    body = args.get("body", "")
    body_format = args.get("body_format", "plain")
    to_list = args.get("to", [])

    msg = MIMEText(body, body_format, "utf-8")
    if to_list:
        msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()

    return {
        "status": "success",
        "draft_id": result.get("id", ""),
        "message": "草稿已建立",
    }


def main():
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        args = {}

    action = args.get("action", "list")

    try:
        service = _get_service()
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return

    actions = {
        "list": action_list,
        "search": action_search,
        "read": action_read,
        "send": action_send,
        "reply": action_reply,
        "draft": action_draft,
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
