"""Diagnose Outlook token refresh + Graph API directly."""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from datetime import datetime, timezone

import aiohttp

from core.database import get_db_session
from core.models import IntegrationToken
from core.privsec.token_encryption import decrypt_token, encrypt_token


async def main() -> None:
    with get_db_session() as db:
        t = (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.provider == "outlook",
                IntegrationToken.status == "active",
            )
            .first()
        )
        if not t:
            print("NO active outlook token in DB")
            return

        exp = t.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        print("user_id:", t.user_id)
        print("expires_at:", exp)
        print("now:      ", now)
        print("expired:", exp < now)
        print("scope:", t.scope)
        rt = decrypt_token(t.refresh_token, allow_plaintext=True) if t.refresh_token else None
        print("has refresh_token:", bool(rt), "len:", len(rt) if rt else 0)

    if not rt:
        print("No refresh token -> must reconnect")
        return

    # 1) Try refresh
    tenant = os.getenv("MICROSOFT_TENANT_ID") or "common"
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": os.getenv("MICROSOFT_CLIENT_ID"),
        "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET"),
        "refresh_token": rt,
        "grant_type": "refresh_token",
        "scope": "offline_access user.read mail.read mail.send",
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, data=data) as r:
            body = await r.json()
            print("\n--- REFRESH ---")
            print("status:", r.status)
            if r.status != 200:
                print("error:", body.get("error"))
                print("desc:", body.get("error_description"))
                return
            new_access = body.get("access_token")
            print("new access token OK, expires_in:", body.get("expires_in"))

            # Persist refreshed tokens so the app works
            from datetime import timedelta

            with get_db_session() as db:
                for prov in ("outlook", "microsoft"):
                    rec = (
                        db.query(IntegrationToken)
                        .filter(
                            IntegrationToken.user_id == t.user_id,
                            IntegrationToken.provider == prov,
                        )
                        .first()
                    )
                    if rec:
                        rec.access_token = encrypt_token(new_access)
                        if body.get("refresh_token"):
                            rec.refresh_token = encrypt_token(body["refresh_token"])
                        rec.expires_at = now + timedelta(seconds=int(body.get("expires_in", 3600)))
                        rec.status = "active"
                db.commit()
            print("tokens persisted to DB")

            # 2) Test Graph /me/messages
            print("\n--- GRAPH /me/messages ---")
            async with s.get(
                "https://graph.microsoft.com/v1.0/me/messages?$top=5&$select=subject,receivedDateTime,from",
                headers={"Authorization": f"Bearer {new_access}"},
            ) as gr:
                gbody = await gr.json()
                print("graph status:", gr.status)
                if gr.status != 200:
                    print("graph error:", gbody.get("error", {}).get("code"), "-", gbody.get("error", {}).get("message"))
                else:
                    msgs = gbody.get("value", [])
                    print("messages returned:", len(msgs))
                    for m in msgs:
                        frm = (m.get("from") or {}).get("emailAddress", {}).get("address")
                        print(f"  - {m.get('receivedDateTime')} | {m.get('subject')} | from {frm}")

            # 3) Graph /me profile
            print("\n--- GRAPH /me ---")
            async with s.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {new_access}"},
            ) as pr:
                pbody = await pr.json()
                print("profile status:", pr.status)
                if pr.status == 200:
                    print("displayName:", pbody.get("displayName"))
                    print("mail:", pbody.get("mail"), "| upn:", pbody.get("userPrincipalName"))
                else:
                    print("profile error:", pbody)


if __name__ == "__main__":
    asyncio.run(main())
