---
name: hermes-self-repair
description: "Safely modify Hermes's own configuration, prompts, skills, or cron jobs: proposal file + Telegram approval + git commit + canary verification + rollback. Use whenever the user asks Hermes to fix, tune, or optimize itself."
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [self-repair, self-improvement, safety, git, human-in-the-loop]
    category: autonomous-ai-agents
---

# Hermes Self-Repair (safe self-modification)

Use this skill for ANY change to Hermes's own setup: `~/.hermes/config.yaml`, `profiles/*`, `skills/*`, `cron/jobs.json`, orchestration prompts/scripts under `~/.hermes/deepresearch` or `~/.hermes/marketing-crew`. The binding policy is `~/Hermes/policies/self-repair.md` — never bypass it.

Server-wide self-learning rule: for all Hermes self-repair/config/prompt/crew changes, preserve reusable mistakes and operational lessons as one-line entries under `## Lessons` in `/home/david_master/.hermes/LESSONS.md`, and update the closest durable workflow prompt/script/skill when the lesson affects a recurring workflow. Keep lessons provider-neutral and never store secrets or one-off task progress.

## Preconditions
- `~/.hermes` is a git repo. Verify with `git -C ~/.hermes status --short`. If the tree is dirty with changes you did not make, STOP and report — do not commit someone else's changes.
- Count today's self-repair commits: `git -C ~/.hermes log --since=midnight --oneline | wc -l`. If ≥ 3, STOP: daily limit reached.

## Procedure
1. **Diagnose.** State the problem in one sentence, with evidence (log line, failed run path, error message).
2. **Propose.** Write `~/Hermes/docs/proposals/YYYY-MM-DD-<slug>.md` containing: problem, root cause, exact planned diff (unified format), verification plan (one cheap command or smoke run), rollback command.
3. **Ask approval.** Send the user (Telegram) a message: one-paragraph summary + the diff + the question "Schválit? (ano/ne)". Do NOT proceed on silence, on a vague reply, or on approval of a *previous* proposal.
4. **Apply.** Make exactly the proposed change, nothing more. Commit: `git -C ~/.hermes add -A && git -C ~/.hermes commit -m "self-repair: <slug> (proposal YYYY-MM-DD-<slug>)"`.
5. **Verify (canary).** Run the cheapest check that exercises the change, e.g.:
   - config/profile change → `hermes -p <profile> chat -Q --max-turns 1 -q "Reply OK"`
   - prompt/script change → smoke run of that workflow with minimal turns
   - cron change → `hermes cron list` + next-run sanity check
   Append the result to the proposal file.
6. **Rollback on failure.** `git -C ~/.hermes revert --no-edit <commit>` and notify the user. Never attempt a fix-of-the-fix without a new proposal.

## Forbidden targets
`.env`, `auth*`, `google_*`, `*.db`, gateway/systemd units, `~/Hermes/policies/`, `~/Hermes/AGENTS.md`, framework code in `~/.hermes/hermes-agent/`, and `hermes update` (always a manual user action).
