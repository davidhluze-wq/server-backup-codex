# Infrastructure crew (vm12890)

Správa VPS, na kterém crews běží: nasazování, Postgres, sjednocení dashboardů, monitoring.
Stejný vzor jako `marketing-crew` — **Python runner + Hermes profily po rolích**
(volání `hermes -p <profil> chat -Q …`), durable artefakty do `runs/`.

> Runner produkuje **plán/příkazy** (deploy unity, SQL, Caddyfile), **nevykonává** je sám.
> Nevratné a síťově-exponované kroky vykonáš ty po schválení dle `~/Hermes/policies/human-in-the-loop.md`.

## Role → profil
| Role | Profil | Úkol |
|---|---|---|
| Deploy/Runner | `deepresearch-claude-opus` | nasazení řešení jako systemd/docker + health check |
| DB Steward | `deepresearch-gpt55` | DB per projekt, migrace, zálohy, uživatelé/hesla |
| Dashboard Curator | `deepresearch-claude-opus` | sjednocení dashboardů pod Caddy s TLS+auth |
| Infra Monitor | zero-LLM (`monitor.sh`) | uptime portů/procesů, alert do Telegramu |

## Spuštění
```bash
cd ~/.hermes/infrastructure   # nebo ~/Hermes/projects/infrastructure (symlink)
python3 scripts/run_infra.py --mode deploy    --task "nasad X jako systemd sluzbu"
python3 scripts/run_infra.py --mode db        --task "zaloz DB finance + uzivatele"
python3 scripts/run_infra.py --mode dashboard --task "pridej marketing metriky pod Caddy"
python3 scripts/run_infra.py --mode full      --task "..."   # deploy+db+dashboard
```
Výstup: `runs/<mode>-<timestamp>/<role>.md` + `summary.json`, souhrn do Telegramu.

## Monitor (zero-LLM, na cron)
```bash
# Hermes cron (preferuj) nebo crontab:
*/5 * * * * /home/david_master/.hermes/infrastructure/scripts/monitor.sh
```
Kontroluje porty (5432, 8802, 8765, 8808, 8642) a procesy (gateway, bridge).
HTTP 401 = služba běží (má Basic Auth) → OK. Mlčí, dokud je vše v pořádku.

## Security setup (krok 0 této crew)
`scripts/01-security-fix.sh` — **vyžaduje sudo + tvé schválení**, proto ho spouštíš ty.
Reálný stav: `:8765` i `:8808` už mají Basic Auth, Postgres je jen na localhostu.
Zbývá dořešit: **TLS** (Caddy), **firewall** (ufw není nainstalován), **default DB heslo**.

## Governance
Vše dle `~/Hermes/AGENTS.md` + `policies/` (model-routing, token-budget, self-repair,
human-in-the-loop). Změny infry jen se schválením přes Telegram.
