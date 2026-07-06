# DeepResearch Workflow v0.1.0

## DAG

1. `research_a` a `research_b` běží paralelně a nezávisle.
2. `arbitrator` porovná oba research výstupy a rozhodne, co smí do finálního reportu.
3. `source_auditor` skepticky zkontroluje zdroje a citace.
4. `final_writer` píše final report pouze z ověřených tvrzení.
5. `quality_reviewer` hodnotí celý run pro Codex Master kontrolora.

## Run artefakty

Každý run ukládá:

- `input.md`
- `research_a.md`
- `research_b.md`
- `arbitration.md`
- `source_audit.md`
- `final_report.md`
- `quality_review.md`
- `run_manifest.json`
- `logs/*.stderr.txt`

## Stav MVP

- Orchestrace: lokální Python wrapper.
- Paralelismus: `ThreadPoolExecutor`, dva nezávislé `hermes chat -Q` subprocessy.
- Tools: `web` toolset pro research a source audit.
- Profily/modely: kombinace `deepresearch-gpt55` (`gpt-5.5`) a `deepresearch-claude-opus` (`claude-opus-4-8`).
- Source audit: hybrid LLM + deterministický `source_url_audit.py`.
- Export: `final_report.html`, `final_report.pdf`, volitelný upload do Google Drive safe folder.

## Budoucí kanban varianta

`hermes kanban swarm` podporuje paralelní workers → verifier → synthesizer. Pro plnou produkci doporučeno doplnit:

- samostatné profily `researcher`, `verifier`, `writer`, případně rozdílné modely,
- exportní hook z kanban do `~/.hermes/deepresearch/runs/`,
- extra navazující karty Source Auditor a Quality Reviewer.
