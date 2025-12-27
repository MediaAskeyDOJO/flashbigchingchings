# communications/ workflow (overview)

## Purpose
- Files placed in `communications/*.md` by the authorized user (e.g. base44) are the repo's communication hub.
- A GitHub Actions workflow detects new/changed communications Markdown, sends it to Claude API, and then:
  - writes the Claude response JSON into `outputs/`, and/or
  - creates a GitHub Issue with the result (configurable).

## Setup Checklist

1. **Add repo secrets** (Settings -> Secrets -> Actions):
   - `CLAUDE_API_KEY` - Your Anthropic API key (same as ANTHROPIC_API_KEY)
   - `ALLOWED_PUSHER` - (optional) GitHub username allowed to trigger (e.g. base44)

2. **Ensure Base44 has write access:**
   - Add the Base44 GitHub account as a collaborator with write access, OR
   - Use a workflow where Base44 opens PRs which are merged by a maintainer

3. **Configure output behavior** (in workflow file):
   - `COMMIT_OUTPUTS: 'true'` - Commit outputs back to repo
   - `OUTPUT_TO_ISSUES: 'true'` - Create Issues with results

## How It Works

1. Base44 pushes a `.md` file to `communications/` folder
2. GitHub Action triggers automatically
3. Python script reads the markdown file
4. Sends content to Claude API
5. Saves response to `outputs/` folder
6. Optionally creates a GitHub Issue with the result

## Security Notes
- Validate `ALLOWED_PUSHER` to limit who can trigger processing
- Never store API keys in repo; use Actions secrets
- Sanitize or review incoming content if you will auto-commit
