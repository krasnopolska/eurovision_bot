---
name: rebase-and-commit
description: Rebase the current branch onto origin/main, refresh CLAUDE.md sections that are now stale, then create a conventional commit (with CHANGELOG entry) for any pending work. Invoke when the user says /rebase-and-commit or asks to "sync, update docs, and commit" in one shot.
---

# rebase-and-commit

Combines three things into one flow: rebase onto upstream, light docs refresh, then a clean commit using this repo's existing conventions.

Never run destructive operations the user hasn't already authorized. If anything is ambiguous (conflicts, divergent history, dirty tree with unrelated changes), stop and ask.

## Preconditions to check first

Run these in parallel and report what you find before touching anything:

- `git status --short` — is the working tree clean, or are there pending changes?
- `git rev-parse --abbrev-ref HEAD` — what branch are we on? Refuse to run on `main` itself; bail with a message asking the user to switch branches.
- `git log --oneline origin/main..HEAD` — what's already committed on this branch?

If the working tree has changes, treat them as in-flight work that should be committed at the end. Do NOT stash and silently drop them.

## Step 1 — Rebase onto origin/main

1. `git fetch origin` to refresh the remote ref.
2. If the working tree is dirty: `git stash push --include-untracked -m "rebase-and-commit: pre-rebase"` so the rebase can run. Remember to pop it at the end.
3. `git rebase origin/main`.
4. **On conflict:** stop immediately. Report which files conflicted (`git diff --name-only --diff-filter=U`) and ask the user how to proceed. Do not attempt to resolve conflicts without explicit guidance.
5. On success, continue.

If the branch is already up to date, say so and skip to step 2 — no shame in a no-op rebase.

## Step 2 — Refresh CLAUDE.md (light scope)

Light means: only update sections whose subject matter was touched by the diff. Do not rewrite untouched sections, even if they look outdated.

1. Compute the change surface: `git diff --name-only origin/main...HEAD` plus any unstashed working-tree changes from step 1.
2. Read `CLAUDE.md`.
3. For each changed file, ask: does CLAUDE.md mention this file, the commands that run it, the env vars it reads, or APIs it exposes? If yes, check whether the mention is still accurate; if not, edit just that section.

Common triggers to look for:
- **`requirements.txt` / `pyproject.toml` changed** → update the "Running the bot" section if install commands changed.
- **`bot.py` env-var reads added/removed/renamed** → update the secrets/env section.
- **`data.py` schema changes** → update the architecture section's table list.
- **New `Dockerfile` / `docker-compose.yml` / config files** → update the run instructions and the "Files" section if it exists.
- **New top-level commands or CLI flags** → update any command/usage tables.
- **`COUNTRIES` list or scoring constants changed in `bot.py` / `data.py`** → update the corresponding explanation in CLAUDE.md.

If nothing in `CLAUDE.md` is affected by the diff, leave it alone. Do not invent updates to look busy.

## Step 3 — Pop the stash (if you stashed in step 1)

`git stash pop`. If pop produces conflicts, stop and ask the user — same rule as rebase conflicts.

## Step 4 — Commit using the repo's existing workflow

Follow the global commit workflow defined in `~/.claude/CLAUDE.md`:

1. `git diff HEAD` to review everything that will be committed (including CLAUDE.md updates from step 2 and any working-tree changes from step 1).
2. Update `CHANGELOG.md` with an entry under `## [Unreleased]` describing the change in user-facing language, present tense. Create the file if it doesn't exist.
3. Stage everything you intend to commit by listing files explicitly — do not use `git add -A` or `git add .`. Watch for sensitive files (`.env`, credentials, large binaries) and warn the user before staging them.
4. Pick a conventional commit type/scope based on the dominant change:
   - `feat(scope):` new behavior the user can see
   - `fix(scope):` bug fix
   - `refactor(scope):` no behavior change
   - `docs(scope):` docs-only (use this if the commit is purely a CLAUDE.md refresh)
   - `chore(scope):` tooling, config, ignore lists
   - `test(scope):` test additions/changes
5. Write the message with a HEREDOC so newlines render correctly. End with the `Co-Authored-By` trailer from the global workflow.
6. Do NOT use `--no-verify` or `--amend`. If a pre-commit hook fails, fix the underlying issue and make a new commit.

## Step 5 — Report back

Tell the user:
- New HEAD SHA and one-line message.
- Whether CLAUDE.md was touched, and which section(s).
- Whether the branch is now ahead of origin/main and ready to push (do **not** push without an explicit request).

Keep the summary to a few lines — the diff and `git log` are right there for the user.

## When to refuse / bail

- Working tree dirty AND the dirty files overlap with unmerged paths from a previous failed rebase → ask the user to resolve manually first.
- On `main` branch → refuse and ask them to create/switch to a feature branch.
- Rebase conflict, stash-pop conflict, hook failure → stop, surface details, wait for instructions.
- More than ~10 files touched by the diff → confirm scope with the user before doing the CLAUDE.md scan, in case this was meant to be split into multiple commits.
