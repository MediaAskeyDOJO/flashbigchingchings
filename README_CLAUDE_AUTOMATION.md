# Claude Automation (Auto-process Markdown)

## What This Does

On every push or pull request that includes `.md` file changes:
1. The GitHub Action triggers automatically
2. Changed Markdown files are read
3. Large files are split into chunks (configurable size)
4. Each chunk is summarized by Claude
5. Chunk summaries are combined into an overall summary
6. Summaries are saved to `.claude-summaries/<path>.summary.md`
7. Summaries are committed back to the branch

## Setup

### 1. Add the ANTHROPIC_API_KEY Secret

1. Go to your repo: Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key

### 2. (Optional) Configure Variables

Go to Settings → Secrets and variables → Actions → Variables tab:

- `CLAUDE_MODEL`: Model to use (default: `claude-sonnet-4-20250514`)
- `CHUNK_SIZE_CHARS`: Characters per chunk (default: `8000`)

## Testing

1. Edit any `.md` file in the repo
2. Push the change
3. Check the Actions tab to see the workflow run
4. A new file will appear in `.claude-summaries/`

## Notes

- Fork PRs won't commit summaries (GitHub security restriction)
- The `[skip ci]` tag prevents infinite loops from summary commits
- Large files are automatically chunked and hierarchically summarized
