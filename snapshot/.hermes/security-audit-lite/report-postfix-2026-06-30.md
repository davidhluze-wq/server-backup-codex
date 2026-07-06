# Security audit lite – kontrola po opravách

- Report vytvořen: `2026-06-30 22:06 UTC`
- Audit byl read-only: nic dalšího jsem neměnil.

## Shrnutí pro Telegram
🟡 – Root je stále aktuálně přihlášený přes SSH z veřejné IP; ověř, že je to záměrné.
🟡 – Firewall/UFW se bez sudo hesla nepodařilo ověřit.
🟢 – Aktualizace jsou hotové: `0` balíků k aktualizaci.
🟢 – Restart proběhl a server běží na kernelu `5.15.0-185`.
🟢 – `fail2ban` služba je aktivní.
🟢 – Port `8765` je záměrně veřejný dashboard a bez přihlášení vrací `401`.

❓ Mám opravit vše, co půjde? (napiš ano)

## Detaily ověření

- Boot time: `2026-06-30 22:04:07`.
- Uptime při kontrole: cca 1 minuta po restartu.
- `apt list --upgradable`: `0`.
- `apt-get -s upgrade`: `0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded`.
- `/var/run/reboot-required`: neexistuje, restart už není požadován.
- `systemctl is-active fail2ban`: `active`.
- Port `8765`: naslouchá na `0.0.0.0:8765`, což je dle uživatele záměrné; lokální HTTP probe vrací `401`, tedy vyžaduje přihlášení.
- SSH port `22`: veřejně dostupný, očekávané.
- Root relace: `root pts/3 217.26.221.27 Tue Jun 30 22:04 still logged in`.
- Firewall/UFW: nelze ověřit bez sudo hesla (`sudo: a password is required`).

## Doporučené další ruční ověření

V terminálu můžeš spustit:

```bash
sudo ufw status verbose
sudo fail2ban-client status sshd
sudo sshd -T | grep permitrootlogin
```

Pokud chceš zakázat přímé root SSH přihlášení, použij:

```bash
sudo tee /etc/ssh/sshd_config.d/99-disable-root-login.conf >/dev/null <<'EOF'
PermitRootLogin no
EOF
sudo sshd -t
sudo systemctl reload ssh
sudo sshd -T | grep permitrootlogin
```
