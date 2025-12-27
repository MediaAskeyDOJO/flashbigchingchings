#!/usr/bin/env node
// Chunk-aware Markdown processor for GitHub Actions.
// - Detects changed .md files (push or PR).
// - Splits large files into chunks (CHUNK_SIZE_CHARS).
// - Summarizes each chunk with Anthropic/Claude.
// - Produces an overall summary by combining chunk summaries.
// - Commits summaries back to the branch.

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const CLAUDE_MODEL = process.env.CLAUDE_MODEL || 'claude-sonnet-4-20250514';
const CHUNK_SIZE = parseInt(process.env.CHUNK_SIZE_CHARS || '8000', 10);

if (!ANTHROPIC_API_KEY) {
  console.error('ANTHROPIC_API_KEY not set. Exiting.');
  process.exit(1);
}

// Get changed .md files
function getChangedMdFiles() {
  const eventName = process.env.GITHUB_EVENT_NAME;
  let diffCmd;
  
  if (eventName === 'pull_request') {
    const base = process.env.GITHUB_BASE_REF;
    diffCmd = `git diff --name-only origin/${base}...HEAD`;
  } else {
    diffCmd = 'git diff --name-only HEAD~1 HEAD';
  }
  
  try {
    const output = execSync(diffCmd, { encoding: 'utf8' });
    return output.split('\n').filter(f => f.endsWith('.md') && fs.existsSync(f));
  } catch (e) {
    console.error('Error getting changed files:', e.message);
    return [];
  }
}

// Split text into chunks
function chunkText(text, size) {
  const chunks = [];
  for (let i = 0; i < text.length; i += size) {
    chunks.push(text.slice(i, i + size));
  }
  return chunks;
}

// Call Claude API
async function callClaude(prompt, content) {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: `${prompt}\n\n${content}`
      }]
    })
  });
  
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Claude API error: ${response.status} - ${err}`);
  }
  
  const data = await response.json();
  return data.content[0].text;
}

// Process a single file with chunking
async function processFile(filePath) {
  console.log(`Processing: ${filePath}`);
  const content = fs.readFileSync(filePath, 'utf8');
  
  let summary;
  
  if (content.length <= CHUNK_SIZE) {
    // Small file - direct summary
    summary = await callClaude('Summarize this Markdown document concisely:', content);
  } else {
    // Large file - chunk and hierarchical summarize
    const chunks = chunkText(content, CHUNK_SIZE);
    console.log(`  File split into ${chunks.length} chunks`);
    
    const chunkSummaries = [];
    for (let i = 0; i < chunks.length; i++) {
      console.log(`  Summarizing chunk ${i + 1}/${chunks.length}...`);
      const chunkSummary = await callClaude(
        `Summarize this section (chunk ${i + 1} of ${chunks.length}):`,
        chunks[i]
      );
      chunkSummaries.push(chunkSummary);
    }
    
    // Combine chunk summaries into final summary
    summary = await callClaude(
      'Combine these section summaries into a cohesive overall summary:',
      chunkSummaries.join('\n\n---\n\n')
    );
  }
  
  // Write summary file
  const summaryDir = '.claude-summaries';
  const summaryPath = path.join(summaryDir, filePath.replace(/\.md$/, '.summary.md'));
  
  fs.mkdirSync(path.dirname(summaryPath), { recursive: true });
  fs.writeFileSync(summaryPath, `# Summary of ${filePath}\n\n${summary}\n`);
  
  console.log(`  Summary written to: ${summaryPath}`);
  return summaryPath;
}

// Commit and push summaries
function commitSummaries(summaryPaths) {
  if (summaryPaths.length === 0) return;
  
  // Check if this is a fork PR (can't push)
  const eventName = process.env.GITHUB_EVENT_NAME;
  if (eventName === 'pull_request') {
    const eventPath = process.env.GITHUB_EVENT_PATH;
    const event = JSON.parse(fs.readFileSync(eventPath, 'utf8'));
    if (event.pull_request?.head?.repo?.fork) {
      console.log('Fork PR detected - skipping commit (no write access)');
      return;
    }
  }
  
  try {
    execSync('git config user.name "Claude Bot"');
    execSync('git config user.email "claude-bot@users.noreply.github.com"');
    execSync(`git add ${summaryPaths.join(' ')}`);
    execSync('git commit -m "Add Claude summaries [skip ci]"');
    execSync('git push');
    console.log('Summaries committed and pushed.');
  } catch (e) {
    console.error('Error committing summaries:', e.message);
  }
}

// Main
async function main() {
  const changedFiles = getChangedMdFiles();
  
  if (changedFiles.length === 0) {
    console.log('No changed .md files found.');
    return;
  }
  
  console.log(`Found ${changedFiles.length} changed .md file(s)`);
  
  const summaryPaths = [];
  for (const file of changedFiles) {
    try {
      const summaryPath = await processFile(file);
      summaryPaths.push(summaryPath);
    } catch (e) {
      console.error(`Error processing ${file}:`, e.message);
    }
  }
  
  commitSummaries(summaryPaths);
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
