# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `finalists.json` config holding the contest year and the finalist list with flag emojis. `bot.py` now loads countries and the year from this file at startup (overridable via `FINALISTS_PATH`); future years only need a JSON edit, no code change.
- Shared Claude Code skill `/rebase-and-commit` under `.claude/skills/`. Rebases the current branch onto `origin/main`, lightly refreshes `CLAUDE.md` for sections affected by the diff, then creates a conventional commit with a `CHANGELOG.md` entry.
- `.gitignore` rule for `.claude/settings.local.json` so each developer's local permission settings stay private while shared skills remain tracked.

### Changed
- All user-facing text now uses the year from `finalists.json` instead of a hardcoded `2026`. The startup loader fails fast on missing/malformed config or duplicate country entries.
- **Scoring is now fair against partial predictions.** Predictions for countries outside the official top-10, and unfilled slots, both count as 0 points. The average is always divided by 10 (the top-N), so a user who submits only one lucky guess no longer scores 100% — they're now compared against a baseline of 10 perfect predictions.
- **Same country can no longer occupy multiple prediction slots.** Database constraint `UNIQUE(user_id, country)` enforces this; the bot now auto-moves the country to the new slot and tells the user "🔁 Moved! Country: #X → #Y". Already-placed countries are marked with ✅ in the country picker.

### Fixed
- `predictions.place` is now constrained to `1..10` at the database level (`CHECK(place BETWEEN 1 AND 10)`); a malicious callback can no longer write garbage place values.
- Legacy databases are migrated transparently on next start (`init_db()` detects old schema and rebuilds the `predictions` table, de-duplicating any `(user_id, country)` pairs by keeping the most recent row).

### Changed (admin UX)
- **`/setresults` is now an interactive wizard, not a text command.** Admin types `/setresults`, taps each place to pick a country from the inline keyboard, and the **Save Results** button stays disabled until all 10 slots are filled. Fixes the old text-parser bugs (multi-word names like "Велика Британія" silently corrupting downstream args, missing-match fuzzy-fallbacks silently writing wrong rows, place/country mismatches from `int()` crashes).
- The wizard de-duplicates picks automatically — choosing a country already used in another slot moves it.
- If official results are already saved, `/setresults` first asks "⚠️ Replace existing results?" with Yes/No, so a re-run no longer accidentally wipes the table.
- `/winner` no longer shows a partial leaderboard. If fewer than 10 official results are stored (e.g. from a legacy partial entry), the command replies "⏳ Results not complete yet — N/10 places entered" and waits for the admin to finish.

### Removed
- Stop tracking `eurovision.db` in git. The SQLite database is now gitignored; existing local copies are preserved on disk but no longer committed.
