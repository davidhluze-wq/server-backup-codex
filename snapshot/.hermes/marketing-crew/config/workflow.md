# Marketing Crew Workflow v0.1.0

## DAG

```text
input.md + website_probe.json/md
  ├─ Website Auditor / QA Agent
  ├─ SEO and Content Agent
  ├─ Competitor / Market Agent
  └─ Messaging / Conversion Agent
        ↓
  Strategy Synthesizer / Manager
        ↓
  Quality Reviewer
        ↓
  audit_report.md/html/pdf + quality_review.md + run_manifest.json
```

## CrewAI-inspired design

- Agent = role + goal + backstory-like operating prompt.
- Task = concrete output file with acceptance criteria.
- Crew = ordered graph with parallel specialists and a manager/synthesizer.
- Process = hybrid parallel/sequential: specialists run in parallel, manager synthesizes, reviewer critiques.

## Safety

- No public ports.
- No login or password typing.
- Do not submit real lead/contact forms.
- Do not perform intrusive scanning; only normal HTTP GET/HEAD style checks and rendered/browser-independent inspection.
- Competitive research uses public web info only.
