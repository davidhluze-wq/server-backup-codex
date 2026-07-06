# Calendar integration operational notes

## User-facing expectations

- Explain in Czech.
- Give exact clicks/commands.
- Make Outlook work-calendar uncertainty explicit: company policy may block publishing or OAuth.
- Prefer read-only calendar access unless the user asks for event creation/editing.

## Google Calendar OAuth notes

Known pitfall: the `google-workspace` SKILL.md may mention `--services calendar --format json`, but the installed `scripts/setup.py` may not accept those flags. Check `setup.py --help` before using them.

If system `python` is missing or system Python has no pip, use Hermes' venv Python:

```bash
PY="$HOME/.hermes/hermes-agent/venv/bin/python"
SETUP="$HOME/.hermes/skills/productivity/google-workspace/scripts/setup.py"
$PY "$SETUP" --check
$PY "$SETUP" --client-secret /path/to/client_secret.json
$PY "$SETUP" --auth-url
$PY "$SETUP" --auth-code 'http://localhost:1/?code=...&state=...'
```

Store Google client secret at:

```bash
install -m 600 client_secret.json ~/.hermes/google_client_secret.json
```

### Manual calendar-only URL generation

Use this if the setup script requests all Workspace scopes but the user only wants Calendar:

```python
from pathlib import Path
import json
from hermes_constants import get_hermes_home
from google_auth_oauthlib.flow import Flow

H = Path(get_hermes_home())
client = H / 'google_client_secret.json'
pending = H / 'google_oauth_pending.json'
last = H / 'google_oauth_last_url.txt'
scopes = ['https://www.googleapis.com/auth/calendar']
flow = Flow.from_client_secrets_file(
    str(client),
    scopes=scopes,
    redirect_uri='http://localhost:1',
    autogenerate_code_verifier=True,
)
url, state = flow.authorization_url(access_type='offline', prompt='consent')
pending.write_text(json.dumps({
    'state': state,
    'code_verifier': flow.code_verifier,
    'redirect_uri': 'http://localhost:1',
}, indent=2))
last.write_text(url)
print(url)
```

Then run the normal exchange:

```bash
$PY "$SETUP" --auth-code 'FULL_REDIRECT_URL'
```

## Outlook / Microsoft 365

### Read-only ICS path

Outlook Web path:

1. Calendar → gear icon
2. View all Outlook settings
3. Calendar → Shared calendars
4. Publish a calendar
5. Choose calendar and permission: Can view all details
6. Copy ICS link

If missing, likely disabled by tenant policy.

### Microsoft Graph OAuth path

For full access or when ICS is blocked:

- App registration in Microsoft Entra ID
- Native/public redirect URI: `http://localhost`
- Delegated permissions: `User.Read`, `offline_access`, `Calendars.Read` or `Calendars.ReadWrite`
- Public client flow enabled
- Expect admin consent in workplace tenants
- User provides Tenant ID and Client ID, not a client secret for public-client flow
