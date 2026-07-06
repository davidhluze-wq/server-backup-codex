---
name: calendar-integrations
description: "Set up calendar access for Hermes across Google Calendar and Outlook/Microsoft 365."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [calendar, google-calendar, outlook, microsoft-365, oauth, ics]
    created_by: agent
---

# Calendar Integrations

Use this skill when a user wants Hermes to read, summarize, or manage calendar events across Google Calendar and Outlook/Microsoft 365.

## Principles

1. **Use least privilege first.** Calendar read-only is enough for availability checks and daily agendas; request write access only when the user explicitly wants Hermes to create/update/delete events.
2. **Never ask the user to paste passwords or secrets into chat.** OAuth redirect URLs/codes are okay; raw client secrets should be handled as uploaded files when possible and stored with `chmod 600`.
3. **For workplace Outlook calendars, expect policy blocks.** Try ICS read-only first; use Microsoft Graph OAuth only when ICS is blocked or write access is required.
4. **Confirm side effects.** Do not create, update, delete, invite attendees, or share calendar data without explicit confirmation.
5. **For this user:** reply in Czech with exact steps/commands and concise status summaries.

## Google Workspace calendar/Gmail/Drive setup

Primary implementation is the existing `google-workspace` skill. Load it first when available, then follow this workflow. This skill can also guide incremental scope upgrades, such as adding Gmail read-only or a least-privilege Drive safe folder after Calendar is already authorized:

1. Store the downloaded Google Desktop OAuth client JSON at:
   `~/.hermes/google_client_secret.json`
2. Set restrictive permissions:
   `chmod 600 ~/.hermes/google_client_secret.json`
3. Prefer the Hermes venv Python if system `python`/`pip` is missing:
   `~/.hermes/hermes-agent/venv/bin/python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py ...`
4. Check auth:
   `.../setup.py --check`
5. Generate auth URL:
   `.../setup.py --auth-url`
6. User opens the URL, grants access, then sends the full `http://localhost:1/?code=...&state=...` redirect URL.
7. Exchange it:
   `.../setup.py --auth-code 'FULL_REDIRECT_URL'`
8. Verify with `--check` and, if available, `--check-live`.

### Calendar-only / incremental-scope caveat

Some installed versions of `google-workspace/scripts/setup.py` do **not** support `--services calendar --format json` and request all Workspace scopes by default. If the user wants narrower consent, manually generate an OAuth URL using `google_auth_oauthlib.flow.Flow` and the Hermes venv Python.

Useful scopes:

- Calendar read/write: `https://www.googleapis.com/auth/calendar`
- Gmail read-only: `https://www.googleapis.com/auth/gmail.readonly`
- Least-privilege Drive write area: `https://www.googleapis.com/auth/drive.file` (not full `drive`)

Manual URL generation pattern:

- redirect URI: first try the exact redirect in the client JSON, often `http://localhost`; use `http://localhost:1` only if registered/working
- `autogenerate_code_verifier=True`
- `include_granted_scopes="true"` when adding Gmail/Drive to an existing Calendar token
- save pending auth data to `~/.hermes/google_oauth_pending.json` with `state`, `code_verifier`, and `redirect_uri`
- save the URL to `~/.hermes/google_oauth_last_url.txt`
- `chmod 600` both pending files

Then use the normal `setup.py --auth-code 'FULL_REDIRECT_URL'` exchange; it reads the pending auth file. If Google consent hangs on `consentsummary`, regenerate with `redirect_uri="http://localhost"` when the client JSON contains that redirect, then ask the user to copy the final `http://localhost/?state=...&code=...` URL.

## Outlook / Microsoft 365 setup

### Option A — ICS read-only link

Use first when the user only needs Hermes to see events.

User steps in Outlook Web:

1. Go to `https://outlook.office.com/calendar/`
2. Settings gear → **View all Outlook settings**
3. **Calendar → Shared calendars**
4. **Publish a calendar**
5. Select the calendar and permission such as **Can view all details**
6. Publish and send Hermes the `.ics` URL

Treat the ICS URL as a bearer secret. If the option is missing, the workplace tenant likely blocks publishing.

### Option B — Microsoft Graph OAuth

Use when ICS is blocked or write access is required. Expect admin consent.

Azure/Entra setup:

1. Microsoft Entra ID → App registrations → New registration
2. Redirect URI: native/public client, usually `http://localhost`
3. Delegated Microsoft Graph permissions:
   - `User.Read`
   - `offline_access`
   - `Calendars.Read` or `Calendars.ReadWrite`
4. Enable public client flows if using device/native flow.
5. Ask for Tenant ID and Client ID. Do **not** ask for a client secret for public-client flows.

If authorization is blocked by admin consent, tell the user to request IT approval or fall back to ICS if available.

## Verification

For Google, after OAuth:

```bash
GAPI="~/.hermes/hermes-agent/venv/bin/python ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
$GAPI calendar list
$GAPI gmail search 'newer_than:30d' --max 1          # if gmail.readonly was granted
$GAPI drive search "name='Hermes Safe Folder' and mimeType='application/vnd.google-apps.folder' and trashed=false" --raw-query --max 10
```

For Drive write access, prefer `drive.file` plus a dedicated safe folder instead of full-drive scope:

```bash
$GAPI drive create-folder 'Hermes Safe Folder'
```

Store the resulting folder ID in memory and write/upload only there unless the user explicitly directs otherwise.

For Outlook ICS, fetch and parse only after the user provides the link, then confirm you can see upcoming events without exposing private details in chat unnecessarily.

## References

- `references/calendar-integrations.md` — condensed operational notes and troubleshooting for Google Calendar + Outlook setup.
- `references/google-workspace-incremental-scopes.md` — manual PKCE OAuth pattern for Calendar + Gmail read-only + Drive `drive.file`, including API enablement and safe-folder verification.
