import fs from 'node:fs';
import { gitRoot, loadConfig, safePath, git } from './lib.mjs';
import { checkState } from './config-validation.mjs';

const results = [];
function read(root, relative) {
  const file = safePath(root, relative);
  if (!fs.existsSync(file)) return '';
  if (fs.statSync(file).size > 1024 * 1024) throw new Error('Oversized integration file');
  return fs.readFileSync(file, 'utf8');
}
try {
  if (process.argv.length !== 2) throw new Error('Usage: node .harness/web/doctor.mjs');
  const root = gitRoot(process.cwd());
  let config;
  try {
    config = loadConfig(root);
    const ready = config.projectName !== 'UNCONFIGURED' &&
      config.checks.some(c => checkState(c) === 'READY') &&
      config.checks.every(c => checkState(c) !== 'GAP');
    results.push({ check: 'configuration', status: ready ? 'PASS' : 'GAP' });
  } catch (error) { results.push({ check: 'configuration', status: 'FAIL', detail: error.message }); }
  if (config) {
    const context = read(root, config.contextPath);
    results.push({ check: 'current-context', status: context.trim() ? 'PASS' : 'GAP', path: config.contextPath });
  }
  const override = read(root, 'AGENTS.override.md');
  const instructions = override.trim() ? override : read(root, 'AGENTS.md');
  results.push({ check: 'root-routing-candidate',
    status: instructions.includes('Docs/Harness/SESSION_BOOTSTRAP.md') ? 'PASS' : 'GAP',
    detail: 'Text presence only; nested/global instructions and live loading still require inspection.' });
  let ignored = false;
  try { ignored = !!git(root, ['check-ignore', '--no-index', '.harness/web/state/probe.json']).trim(); } catch {}
  results.push({ check: 'local-state-ignored', status: ignored ? 'PASS' : 'GAP' });
  const hookText = read(root, '.codex/hooks.json') + '\n' + read(root, '.codex/config.toml');
  results.push({ check: 'optional-hook-references', status: 'INFO',
    detail: hookText.includes('session.mjs') ? 'Reference found; schema, path, trust and execution are NOT verified.' : 'No hook reference found; manual workflow remains available.' });
  let hooksPath = '(Git default)';
  try { hooksPath = git(root, ['config', '--get', 'core.hooksPath']).trim() || hooksPath; } catch {}
  results.push({ check: 'git-hook-location', status: 'INFO', detail: hooksPath });
  results.push({ check: 'runtime/browser/CI', status: 'NOT_VERIFIED',
    detail: 'Read-only static diagnosis executes no checks or hooks. Run live acceptance separately.' });
  const gap = results.some(r => ['GAP', 'FAIL'].includes(r.status));
  console.log(JSON.stringify({ version: 1, mode: 'read-only-static', target: root,
    status: gap ? 'GAPS' : 'STATIC_READY_NOT_ACTIVATED', results }, null, 2));
  process.exitCode = gap ? 2 : 0;
} catch (error) {
  console.error('Doctor failed: ' + error.message);
  process.exitCode = 2;
}
