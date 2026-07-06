# Agent/Profile Mapping

## MVP mapování

| Role | Hermes profil/model | Toolset | Poznámka |
|---|---|---|---|
| Research Agent A | `deepresearch-gpt55` / `gpt-5.5` | `web` | nezávislá strategie: primární a přehledové zdroje |
| Research Agent B | `deepresearch-claude-opus` / `claude-opus-4-8` | `web` | odlišná strategie: protiargumenty, limity, bezpečnost |
| Arbitrator / Verifier | `deepresearch-claude-opus` / `claude-opus-4-8` | `web` | rozhoduje podle kvality důkazů |
| Source Auditor | `deepresearch-claude-opus` / `claude-opus-4-8` + deterministický URL audit | `web` | kontroluje URL, citace, primární/sekundární zdroje |
| Final Writer | `deepresearch-gpt55` / `gpt-5.5` | `web` | používá jen claims povolené arbitrem/auditorem |
| Quality Reviewer | `deepresearch-claude-opus` / `claude-opus-4-8` | `web` | kritická revize workflow |

## Doporučené budoucí profily

- `deepresearch-researcher-fast`: rychlý model pro široký sběr zdrojů.
- `deepresearch-verifier`: silnější model pro rozpory, zdroje a logiku.
- `deepresearch-writer`: silný model pro syntézu a strukturu.
- `deepresearch-reviewer`: skeptický model s nízkou tolerancí k neozdrojovaným tvrzením.
