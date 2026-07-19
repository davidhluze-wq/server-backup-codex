# AgentsMon Dashboard Deployment

The public reverse proxy runs as the user service `agentsmon-dashboard.service`.

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user status agentsmon-dashboard.service
```

The service binds port `8765` and proxies the scoped Next.js Meeting workspace at
`/startup-meetings`. Do not run a detached `nohup` dashboard copy alongside this service.
