# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `finalists.json` config holding the contest year and the finalist list with flag emojis. `bot.py` now loads countries and the year from this file at startup (overridable via `FINALISTS_PATH`); future years only need a JSON edit, no code change.
- Shared Claude Code skill `/rebase-and-commit` under `.claude/skills/`. Rebases the current branch onto `origin/main`, lightly refreshes `CLAUDE.md` for sections affected by the diff, then creates a conventional commit with a `CHANGELOG.md` entry.
- `.gitignore` rule for `.claude/settings.local.json` so each developer's local permission settings stay private while shared skills remain tracked.

### Changed
- All user-facing text now uses the year from `finalists.json` instead of a hardcoded `2026`. The startup loader fails fast on missing/malformed config or duplicate country entries.

### Removed
- Stop tracking `eurovision.db` in git. The SQLite database is now gitignored; existing local copies are preserved on disk but no longer committed.
