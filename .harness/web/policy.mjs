import { pathToFileURL } from 'node:url';
import { gitRoot, git, loadConfig } from './lib.mjs';

export function globMatch(candidate, glob) {
  if (typeof glob !== 'string') throw new Error('Invalid path pattern');
  let expression = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') {
      i++;
      if (glob[i + 1] === '/') { i++; expression += '(?:.*/)?'; }
      else expression += '.*';
    } else if (c === '*') expression += '[^/]*';
    else expression += c.replace(/[\\^$+?.()|{}\[\]]/g, '\\$&');
  }
  return new RegExp('^' + expression + '$', 'i').test(candidate);
}
export function violations(paths, config) {
  return paths.filter(p => !(config.allowedStagedPaths || []).some(g => globMatch(p, g)) && config.deniedStagedPaths.some(g => globMatch(p, g)));
}
export function staged(root) {
  return git(root, ['diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z']).split('\0').filter(Boolean);
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (process.argv.length !== 2) throw new Error('No arguments accepted');
    const root = gitRoot(process.cwd());
    const bad = violations(staged(root), loadConfig(root));
    if (bad.length) {
      console.error('Blocked staged paths:\n' + bad.map(p => JSON.stringify(p)).join('\n'));
      process.exitCode = 1;
    } else console.log('Staged path policy passed; source/runtime checks are separate.');
  } catch (error) {
    console.error('Staged policy failed: ' + error.message);
    process.exitCode = 1;
  }
}
