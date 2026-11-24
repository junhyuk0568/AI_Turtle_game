import fs from 'node:fs';
import path from 'node:path';
import { digest, gitRoot, git, safePath, loadConfig, readJson, atomicJson } from './lib.mjs';

const CONTEXT_LIMIT = 65536;
const PATCH_INPUT_LIMIT = 16 * 1024 * 1024;
function boundedText(file, size = 6000) {
  if (fs.statSync(file).size > CONTEXT_LIMIT) throw new Error('Context exceeds 64 KiB; archive history');
  return fs.readFileSync(file, 'utf8').slice(0, size);
}
async function input(limit) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    bytes += chunk.length;
    if (bytes > limit) throw new Error('Hook input exceeds ' + limit + ' bytes; split this patch');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
function changedPaths(root, cwd, patch, includeDelete) {
  const expression = includeDelete
    ? /^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/gm
    : /^\*\*\* (?:Add File|Update File|Move to): (.+)$/gm;
  return [...patch.matchAll(expression)].map(match => {
    const candidate = match[1].trim().replace(/\\/g, '/');
    // Reject traversal before normalization, preserving the strict policy.
    if (candidate.split('/').includes('..')) throw new Error('Parent traversal refused');
    const absolute = path.isAbsolute(candidate) ? candidate : path.resolve(cwd, candidate);
    const relative = path.relative(root, absolute).split(path.sep).join('/');
    safePath(root, relative);
    return relative;
  });
}
function currentContext(root, config) {
  try { return boundedText(safePath(root, config.contextPath)); }
  catch { return 'Current context unavailable. Read the configured authority directly and inspect Git status.'; }
}
const mode = process.argv[2];
try {
  if (!['start', 'save', 'related', 'guard'].includes(mode)) throw new Error('Invalid hook mode');
  const data = await input(['guard', 'related'].includes(mode) ? PATCH_INPUT_LIMIT : CONTEXT_LIMIT);
  const cwd = fs.realpathSync(data.cwd || process.cwd());
  const root = gitRoot(cwd);
  const config = loadConfig(root);
  const id = typeof data.session_id === 'string' && data.session_id.length <= 4096 ? data.session_id : '';
  const relative = id ? '.harness/web/state/session-' + digest(id) + '.json' : '';
  if (mode === 'save' && data.hook_event_name === 'PreCompact' && id) {
    atomicJson(root, relative, {
      version: 1, root, sessionId: id, at: new Date().toISOString(),
      context: boundedText(safePath(root, config.contextPath)),
      gitStatus: git(root, ['status', '--short', '--untracked-files=no']).slice(0, 2000)
    });
    console.log(JSON.stringify({ systemMessage: 'Bounded same-session recovery aid saved; current documents remain authoritative.' }));
  } else if (mode === 'start' && data.hook_event_name === 'SessionStart') {
    let text = 'Read Docs/Harness/SESSION_BOOTSTRAP.md. Current durable context:\n' + currentContext(root, config);
    if (relative && ['compact', 'resume'].includes(data.source)) {
      // Snapshot errors must never suppress the already-read durable context.
      try {
        const file = safePath(root, relative);
        if (fs.existsSync(file) && fs.statSync(file).size <= CONTEXT_LIMIT) {
          const snapshot = readJson(file);
          if (snapshot.version === 1 && snapshot.sessionId === id && snapshot.root === root &&
              typeof snapshot.context === 'string') {
            text += '\nHistorical same-session snapshot (current documents take precedence):\n' + snapshot.context.slice(0, 1800);
          }
        }
      } catch { text += '\nSnapshot ignored: invalid or unavailable; use current documents.'; }
    }
    console.log(JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'SessionStart', additionalContext: text.slice(0, 9000)
    }}));
  } else if (mode === 'related' && data.hook_event_name === 'PostToolUse' && data.tool_name === 'apply_patch') {
    const changed = changedPaths(root, cwd, String(data.tool_input?.command || ''), true);
    const notes = config.relatedFiles.filter(rule => changed.some(p => p.includes(rule.contains))).map(rule => rule.note);
    if (notes.length) console.log(JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'PostToolUse', additionalContext: notes.join('\n').slice(0, 3000)
    }}));
  } else if (mode === 'guard' && data.hook_event_name === 'PreToolUse' && data.tool_name === 'apply_patch') {
    const { violations } = await import('./policy.mjs');
    if (typeof data.tool_input?.command !== 'string' || !data.tool_input.command.trim()) throw new Error('Missing patch command');
    const bad = violations(changedPaths(root, cwd, data.tool_input.command, false), config);
    if (bad.length) console.log(JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'PreToolUse', permissionDecision: 'deny',
      permissionDecisionReason: 'Path policy blocks: ' + bad.map(p => JSON.stringify(p)).join(', ')
    }}));
  }
} catch (error) {
  if (mode === 'guard') {
    console.log(JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'PreToolUse', permissionDecision: 'deny',
      permissionDecisionReason: 'Path guard could not validate input: ' + error.message
    }}));
  } else console.log(JSON.stringify({ systemMessage: 'Harness hook unavailable: ' + error.message }));
}
