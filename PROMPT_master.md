# ApiHive — Master Orchestrator

You are implementing the ApiHive project from scratch across 5 phases.
The project root is: `C:/Users/rohan/Desktop/personal_projects/claude_projects/apihive`

## Step 1: Determine current phase

Check which files exist to determine where to resume:

- **Phase 1 incomplete** if ANY of these are missing:
  `core/__init__.py`, `core/models.py`, `core/db.py`, `core/script_runner.py`,
  `core/variables.py`, `ui/__init__.py`, `app.py`, `requirements.txt`

- **Phase 2 incomplete** if Phase 1 is done but ANY of these are missing or still stubs:
  `ui/layout.py`, `ui/sidebar.py`, `ui/request_tabs.py`

- **Phase 3 incomplete** if Phase 2 is done but ANY of these are missing or still stubs:
  `core/http_client.py`
  OR `ui/request_builder.py` still contains "coming in Phase 3"
  OR `ui/response_viewer.py` still contains "coming in Phase 3"

- **Phase 4 incomplete** if Phase 3 is done but ANY of these are missing:
  `ui/env_manager.py`
  OR `core/variables.py` is missing `get_active_env_values` or `get_global_values`

- **Phase 5 incomplete** if Phase 4 is done but ANY of these are missing:
  `core/importer.py`, `ui/importer_dialog.py`, `ui/settings.py`
  OR `ui/request_tabs.py` is missing max-tab or dirty-flag logic

- **All phases complete** → output the final promise (see bottom of this file)

## Step 2: Read the phase prompt

Once you know which phase is current, read the corresponding prompt file in full:

- Phase 1 → read `PROMPT_phase1.md`
- Phase 2 → read `PROMPT_phase2.md`
- Phase 3 → read `PROMPT_phase3.md`
- Phase 4 → read `PROMPT_phase4.md`
- Phase 5 → read `PROMPT_phase5.md`

Also read `plan.md` fully — it contains all architecture decisions, data models,
field names, and code sketches. Every phase prompt references it. Follow it exactly.

## Step 3: Implement the current phase

Follow the phase prompt exactly:
- Check every file before writing it
- If a file already exists and is partially correct, continue from where it left off
- Do NOT implement features belonging to a later phase
- Commit and push at the milestones specified in the phase prompt's "Git Commits" section

## Step 4: Verify the phase is done

Run through the "Done when" checklist in the phase prompt.
Only move on once all conditions are satisfied.

## Step 5: Advance or complete

- If Phase 1–4 just completed: this prompt will be fed again automatically.
  On the next iteration you will detect the new phase and continue.
- If Phase 5 just completed and all 15 verification items in plan.md pass,
  run the final commit, then output:

<promise>APIHIVE MVP COMPLETE</promise>

## Important rules

- Never skip a phase or implement features out of order
- Never commit `.env` (it is gitignored) — only `.env.example`
- If a dependency is missing or broken from an earlier phase, fix it before continuing
- All git commands use the path:
  `cd /c/Users/rohan/Desktop/personal_projects/claude_projects/apihive`
