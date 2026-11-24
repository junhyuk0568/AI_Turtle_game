import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { gitRoot, loadConfig, safePath, atomicJson, digest, git } from './lib.mjs';
import { checkState } from './config-validation.mjs';

let report, root, run = false;
try {
  const args = process.argv.slice(2);
  const requested = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--run' && !run) run = true;
    else if (args[i] === '--check' && args[i + 1] && !args[i + 1].startsWith('--')) {
      const name = args[++i];
      if (requested.includes(name)) throw new Error('Duplicate --check name: ' + name);
      requested.push(name);
    } else throw new Error('Usage: node .harness/web/verify.mjs [--run] [--check NAME ...]');
  }
  root = gitRoot(process.cwd());
  // Validate every entry and cwd before executing any configured command.
  const config = loadConfig(root);
  for (const name of requested) {
    if (!config.checks.some(check => check.name === name)) throw new Error('Unknown check: ' + name);
  }
  const rows = config.checks.map(check => ({ check, status: checkState(check),
    selected: !requested.length || requested.includes(check.name) }));
  const selectedRows = rows.filter(row => row.selected);
  const partial = rows.some(row => !row.selected);
  const gaps = [];
  if (config.projectName === 'UNCONFIGURED') gaps.push('projectName is UNCONFIGURED');
  if (!selectedRows.some(row => row.status === 'READY')) gaps.push('No applicable reviewed check');
  for (const row of selectedRows) if (row.status === 'GAP') gaps.push(row.check.name + ' is not configured/reviewed');
  report = {
    version: 1, mode: run ? 'run' : 'preflight', at: new Date().toISOString(),
    id: crypto.randomUUID(), configSha256: digest(JSON.stringify(config)),
    scope: partial ? 'selected' : 'all', allConfiguredChecksPassed: false, requestedChecks: requested,
    checks: rows.map(({ check, status, selected }) => ({ name: check.name, cwd: check.cwd, required: check.required,
      selected, configurationStatus: status,
      commandSha256: digest(JSON.stringify(check.argv)), status: !selected ? 'NOT_SELECTED' : status === 'READY' ? 'NOT_RUN' : status,
      reason: check.skipReason || null })),
    gaps, browser: 'NOT_RUN', status: 'NOT_RUN'
  };
  try { report.commit = git(root, ['rev-parse', 'HEAD']).trim(); } catch { report.commit = null; }
  // Persist fingerprints and outcomes, never raw command arguments or stdout.
  if (gaps.length) {
    gaps.forEach(gap => console.log('GAP: ' + gap));
    console.log('No commands executed because configuration preflight did not pass.');
    report.status = 'GAP';
    process.exitCode = 2;
  } else {
    let failed = false;
    for (let i = 0; i < rows.length; i++) {
      const { check, status, selected } = rows[i], resultRow = report.checks[i];
      if (!selected) { console.log('NOT SELECTED: ' + check.name + ' (' + status + ')'); continue; }
      if (status === 'NOT_APPLICABLE') { console.log('NOT APPLICABLE: ' + check.name); continue; }
      if (!run) { console.log('READY, NOT RUN: ' + check.name); continue; }
      const cwd = check.cwd === '.' ? root : safePath(root, check.cwd);
      console.log('RUN: ' + check.name);
      const started = Date.now();
      const result = spawnSync(check.argv[0], check.argv.slice(1), {
        cwd, stdio: 'inherit', shell: false, windowsHide: true, timeout: check.timeoutMs
      });
      resultRow.durationMs = Date.now() - started;
      resultRow.exitCode = result.status;
      resultRow.errorCode = result.error?.code || null;
      resultRow.signal = result.signal || null;
      resultRow.status = result.error || result.status !== 0 ? 'FAIL' : 'PASS';
      if (resultRow.status === 'FAIL') failed = true;
      console.log(resultRow.status + ': ' + check.name);
    }
    report.status = !run ? (partial ? 'SELECTED_READY_NOT_RUN' : 'READY_NOT_RUN') : failed ? 'FAIL' : partial ? 'PARTIAL_PASS' : 'PASS';
    report.allConfiguredChecksPassed = run && !partial && !failed;
    if (partial) console.log('Partial verification only; omitted checks are not accepted as passed.');
    process.exitCode = failed ? 2 : 0;
  }
  if (!run) console.log('Preflight only; no application checks executed.');
} catch (error) {
  console.error('Verification failed: ' + error.message);
  process.exitCode = 2;
  if (root) report = { version: 1, mode: run ? 'run' : 'preflight', at: new Date().toISOString(),
    id: crypto.randomUUID(), status: 'INVALID_CONFIG', checks: [], browser: 'NOT_RUN' };
}
if (run && root && report) {
  try {
    const relative = '.harness/web/state/verification-' + report.id + '.json';
    atomicJson(root, relative, report);
    console.log('Evidence: ' + relative);
  } catch (error) {
    console.error('Evidence write failed: ' + error.message);
    process.exitCode = 2;
  }
}
