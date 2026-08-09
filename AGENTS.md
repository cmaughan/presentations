# Repository Guidance

If you see improvements in what you've just done, or have ideas for ways it can be done differently, or just knowledge of something related, give me a short note about it. Otherwise, I'm a learner; I want to learn new things, teach me if necessary, and make connections between things if that's appropriate.

## Project Shape

- This repo contains Quarto RevealJS presentations. Each deck lives in its own directory with `index.qmd`, `_quarto.yml`, optional `custom.scss`, and local assets such as `screenshots/`.
- Treat these decks as Quarto presentations, not PowerPoint projects. Edit the Quarto source files directly and do not use PPT/PPTX-specific tooling unless explicitly requested.
- Generated deck output goes under each deck's `_output/` directory and is ignored by git. Do not commit `_output/`, `.quarto/`, or `index_files/`.
- Use `do.py` from the repo root for common deck tasks:
  - `python do.py slides` builds all decks.
  - `python do.py slides fitness` builds one deck.
  - `python do.py slides-preview fitness` starts a Quarto preview for one deck.
  - `python do.py slides-pdf fitness` exports a deck to PDF.

## Fitness Deck

- The fitness deck uses generated Strava charts from `fitness/strava_runs.py`.
- When changing chart behavior, update the generator first, add or update tests in `fitness/tests/test_strava_runs.py`, then regenerate chart assets from `D:\dev\presentations\fitness` with `python strava_runs.py`.
- The interactive chart HTML files in `fitness/screenshots/` are checked in because the deck embeds them directly. Keep them in sync with the generator.
- `fitness/screenshots/plotly.min.js` is the local Plotly bundle for offline playback. Do not switch generated chart HTML back to a CDN dependency.
- Run `python -m unittest discover -s tests` from `fitness` after changes to `strava_runs.py` or generated chart behavior.
- Run `quarto render` from `fitness` after deck, style, or chart asset changes.

## Editing Expectations

- Keep deck edits scoped to the deck being changed unless the shared build helper or root guidance needs updating.
- Preserve the existing RevealJS style in each deck. Prefer small, direct layout fixes over broad restyling unless explicitly requested.
- For generated artifacts, avoid hand-editing checked-in HTML/PNG outputs unless the generator cannot reasonably produce the needed result. If hand-editing is unavoidable, leave a short note explaining why.
