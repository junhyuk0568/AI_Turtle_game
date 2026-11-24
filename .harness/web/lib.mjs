import { validateConfig } from './config-validation.mjs';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

export const digest = value => crypto.createHash('sha256').update(value).digest('hex');
export function safePath(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative) ||
      /^[A-Za-z]:/.test(relative) || relative.includes('\\') ||
      relative.split('/').some(p => p === '..' || p === '.' || !p)) {
    throw new Error('Unsafe relative path: ' + relative);
  }
  const target = path.resolve(root, relative);
  if (!target.startsWith(path.resolve(root) + path.sep)) throw new Error('Path escapes root');
  let current = path.resolve(root);
  if (fs.lstatSync(current).isSymbolicLink()) throw new Error('Root symlink is not supported');
  for (const part of relative.split('/')) {
    current = path.join(current, part);
    try {
      const stat = fs.lstatSync(current);
      if (stat.isSymbolicLink()) throw new Error('Symlink path refused: ' + relative);
      if (current !== target && !stat.isDirectory()) throw new Error('Parent is not a directory: ' + relative);
    } catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
  return target;
}
export function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
}
export function git(root, args) {
  const result = spawnSync('git', ['-C', root, ...args], {
    encoding: 'utf8', windowsHide: true, timeout: 15000, maxBuffer: 2 * 1024 * 1024,
    env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' }
  });
  if (result.error || result.status !== 0) throw new Error('Git read failed: ' + args[0]);
  return result.stdout;
}
export function gitRoot(cwd) {
  return fs.realpathSync(git(cwd, ['rev-parse', '--show-toplevel']).trim());
}
export function loadConfig(root) {
  const config = readJson(safePath(root, '.harness/web/config.json'));
  return validateConfig(root, config, safePath);
}
export function writeNew(root, relative, content) {
  const file = safePath(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, { flag: 'wx' });
}
export function atomicJson(root, relative, value) {
  const file = safePath(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = file + '.' + crypto.randomUUID() + '.tmp';
  try {
    fs.writeFileSync(temp, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
    fs.renameSync(temp, file);
  } finally {
    if (fs.existsSync(temp)) fs.unlinkSync(temp);
  }
}
