import fs from 'node:fs';
const nonempty = value => typeof value === 'string' && value.trim().length > 0;
function patterns(value, field) {
  if (!Array.isArray(value) || value.some(v => !nonempty(v))) throw new Error('Invalid ' + field);
}
export function validateConfig(root, config, safePath) {
  if (!config || config.version !== 1) throw new Error('Invalid config version');
  if (!nonempty(config.projectName)) throw new Error('projectName is required');
  if (!nonempty(config.contextPath)) throw new Error('contextPath is required');
  safePath(root, config.contextPath);
  patterns(config.deniedStagedPaths, 'deniedStagedPaths');
  patterns(config.allowedStagedPaths, 'allowedStagedPaths');
  if (!Array.isArray(config.relatedFiles) || config.relatedFiles.some(rule =>
    !rule || !nonempty(rule.contains) || !nonempty(rule.note))) throw new Error('Invalid relatedFiles');
  if (!Array.isArray(config.checks)) throw new Error('checks must be an array');
  const names = new Set();
  for (const check of config.checks) {
    if (!check || !nonempty(check.name) || names.has(check.name)) throw new Error('Invalid or duplicate check name');
    names.add(check.name);
    if (typeof check.required !== 'boolean' || typeof check.reviewed !== 'boolean') throw new Error('Invalid check flags: ' + check.name);
    if (!Array.isArray(check.argv) || check.argv.some(v => typeof v !== 'string' || v.includes('\0')) ||
      (check.argv.length && !nonempty(check.argv[0]))) throw new Error('Invalid argv: ' + check.name);
    if (check.skipReason !== undefined && !nonempty(check.skipReason)) throw new Error('Invalid skipReason: ' + check.name);
    if (check.skipReason && (check.required || check.argv.length)) throw new Error('N/A must be optional with empty argv: ' + check.name);
    if (!Number.isInteger(check.timeoutMs) || check.timeoutMs < 1000 || check.timeoutMs > 600000) {
      throw new Error('timeoutMs must be 1000..600000: ' + check.name);
    }
    const cwd = check.cwd === '.' ? root : safePath(root, check.cwd);
    if (!fs.existsSync(cwd) || !fs.statSync(cwd).isDirectory()) throw new Error('Check cwd is not a directory: ' + check.name);
  }
  return config;
}
export function checkState(check) {
  if (check.skipReason) return 'NOT_APPLICABLE';
  if (!check.reviewed || !check.argv.length) return 'GAP';
  return 'READY';
}
