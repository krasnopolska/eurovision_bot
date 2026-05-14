# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Shared Claude Code skill `/rebase-and-commit` under `.claude/skills/`. Rebases the current branch onto `origin/main`, lightly refreshes `CLAUDE.md` for sections affected by the diff, then creates a conventional commit with a `CHANGELOG.md` entry.
- `.gitignore` rule for `.claude/settings.local.json` so each developer's local permission settings stay private while shared skills remain tracked.

### Removed
- Stop tracking `eurovision.db` in git. The SQLite database is now gitignored; existing local copies are preserved on disk but no longer committed.
