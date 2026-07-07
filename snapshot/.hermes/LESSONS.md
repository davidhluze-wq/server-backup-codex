# Global Self-Learning Rule

This server uses provider-neutral self-learning for all agents, models, crews, and recurring automations.

## Self-learning
When the user corrects you, you discover a mistake, a tool/process fails, or you learn a reusable operational lesson before continuing:
1. Add a concise one-line lesson under `## Lessons` in `/home/david_master/.hermes/LESSONS.md` so the same issue is not repeated.
2. If the lesson belongs to a recurring workflow, crew, dashboard, automation, or skill, also update the closest durable prompt/skill/script note that controls that workflow.
3. Keep lessons factual and reusable. Do not store secrets, temporary task progress, PR IDs, one-off artifact IDs, or stale details.
4. For providers without file-write tools, clearly return the exact one-line lesson to be added by the orchestrator.

## Lessons
- Automatic/recurring jobs created for David must also be registered in agentsmon dashboard automatic runs with a clear expandable description and Start/Stop controls when technically feasible.
- If `execute_code` is blocked by approval/cron trust policy, switch to explicit read/write/patch/terminal tools instead of retrying the same helper.
- Hermes Architect must ingest `/home/david_master/.hermes/LESSONS.md` as an optimization-idea backlog and convert recurring lessons into propose-only improvements.
