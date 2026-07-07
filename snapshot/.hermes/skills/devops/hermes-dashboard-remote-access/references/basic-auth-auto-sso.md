# Basic Auth auto-SSO pitfall — Hermes Dashboard

## Symptom

When exposing Hermes Dashboard publicly with only the built-in Basic Auth provider configured, unauthenticated navigation to `/sessions` may redirect to:

```text
/auth/login?provider=basic&next=%2Fsessions
```

That endpoint is for OAuth-style providers. Basic Auth is password-only, so the provider raises:

```text
NotImplementedError: BasicAuthProvider is password-only; there is no OAuth redirect flow. The login page POSTs to /auth/password-login instead.
```

Browser result can look like blank page or `500 Internal Server Error`.

## Correct expected flow

For public dashboard with basic auth:

```text
/sessions  -> 302 /login?next=%2Fsessions
/login     -> renders username/password form
POST /auth/password-login -> {"ok":true,"next":"/sessions"} + session cookies
```

## Fix pattern

In the auto-SSO middleware, do not auto-initiate `/auth/login` for password providers. If the only registered provider has `supports_password=True`, return `None` so normal `/login` rendering handles the password form.

Representative patch:

```python
provider = providers[0]
# Password-only providers (e.g. built-in basic auth) do not support the
# OAuth redirect flow behind /auth/login. Let /login render its password
# form instead of auto-SSO redirecting to a 500.
if getattr(provider, "supports_password", False):
    return None
```

## Verification commands

```bash
curl -s http://127.0.0.1:9119/api/status | python3 -m json.tool
curl -s http://127.0.0.1:9119/api/auth/providers | python3 -m json.tool
curl -I 'http://<server-ip>:9119/sessions'
curl -I 'http://<server-ip>:9119/login?next=/sessions'
```

Expected status excerpts:

```json
"auth_required": true,
"auth_providers": ["basic"]
```

Expected providers:

```json
{
  "providers": [
    {"name": "basic", "display_name": "Username & Password", "supports_password": true}
  ]
}
```

## Security note

Public dashboard over plain HTTP is acceptable only as a temporary convenience. For long-term mobile access, prefer HTTPS/reverse proxy or SSH tunnel.