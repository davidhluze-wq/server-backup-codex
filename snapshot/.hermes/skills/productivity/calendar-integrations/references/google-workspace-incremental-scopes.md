# Google Workspace incremental OAuth scopes

Use this when the bundled `google-workspace/scripts/setup.py` cannot generate narrow service-specific auth URLs, or when the user starts with Calendar and later adds Gmail/Drive.

## Use Hermes venv Python

System `python`/`pip` may be missing, while Hermes venv has Google libraries:

```bash
PY="$HOME/.hermes/hermes-agent/venv/bin/python"
SETUP="$HOME/.hermes/skills/productivity/google-workspace/scripts/setup.py"
GAPI="$PY $HOME/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
```

## Store client secret

```bash
install -m 600 client_secret.json "$HOME/.hermes/google_client_secret.json"
$PY "$SETUP" --client-secret "$HOME/.hermes/google_client_secret.json"
```

## Manual narrow OAuth URL

Generate URL with only desired scopes and a pending PKCE session that `setup.py --auth-code` can exchange later:

```python
from pathlib import Path
import json
from hermes_constants import get_hermes_home
from google_auth_oauthlib.flow import Flow

H = Path(get_hermes_home())
client = H / "google_client_secret.json"
pending = H / "google_oauth_pending.json"
last = H / "google_oauth_last_url.txt"
scopes = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]
redirect_uri = "http://localhost"  # match client JSON if Google hangs with localhost:1
flow = Flow.from_client_secrets_file(
    str(client), scopes=scopes, redirect_uri=redirect_uri, autogenerate_code_verifier=True
)
url, state = flow.authorization_url(
    access_type="offline", prompt="consent", include_granted_scopes="true"
)
pending.write_text(json.dumps({
    "state": state,
    "code_verifier": flow.code_verifier,
    "redirect_uri": redirect_uri,
}, indent=2))
last.write_text(url)
pending.chmod(0o600); last.chmod(0o600)
print(url)
```

User opens the URL and returns the full final URL, e.g. `http://localhost/?state=...&code=...&scope=...`.

Then exchange and verify:

```bash
$PY "$SETUP" --auth-code 'FULL_REDIRECT_URL'
$PY "$SETUP" --check-live
$GAPI calendar list
$GAPI gmail search 'newer_than:30d' --max 1
$GAPI drive search "name='Hermes Safe Folder' and mimeType='application/vnd.google-apps.folder' and trashed=false" --raw-query --max 10
```

If Gmail/Drive return `accessNotConfigured`, the user must enable APIs in the Google Cloud project:

- Gmail API: `https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=<PROJECT_NUMBER>`
- Drive API: `https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=<PROJECT_NUMBER>`

## Drive safe folder

Prefer `drive.file`, then create a dedicated folder:

```bash
$GAPI drive create-folder 'Hermes Safe Folder'
```

Store the folder ID in memory and constrain future Drive writes/uploads to that folder unless the user explicitly asks otherwise.
