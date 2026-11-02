/**
 * Guards the trimmed Bootstrap build (src/bootstrap.scss).
 *
 * Run after `vite build`. Fails if the app uses a Bootstrap class that the
 * trimmed stylesheet no longer contains, which would otherwise show up as
 * quietly unstyled UI. Two sources of "used":
 *   1. any word, inside a string literal on a line that sets a class, that is
 *      also a class in the full Bootstrap CSS, and
 *   2. classes that react-bootstrap adds itself (REACT_BOOTSTRAP below).
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

// Classes react-bootstrap emits for the components in use (Alert, Button,
// Card, Form*, InputGroup, Modal, Spinner, Toast, grid). Found by rendering
// every screen and collecting the resulting DOM classes.
const REACT_BOOTSTRAP = [
  'active', 'alert', 'alert-danger', 'btn', 'btn-danger', 'btn-link', 'btn-outline-secondary', 'btn-primary', 'btn-sm',
  'card', 'card-body', 'col-6', 'col-lg-5', 'col-lg-7', 'col-md-3', 'col-md-4', 'col-sm-6', 'container',
  'container-fluid', 'end-0', 'fade', 'form-check', 'form-check-input', 'form-check-label', 'form-control',
  'form-label', 'form-select', 'form-switch', 'form-text', 'input-group', 'modal', 'modal-backdrop', 'modal-body',
  'modal-content', 'modal-dialog', 'modal-dialog-centered', 'modal-footer', 'row', 'show', 'spinner-border',
  'spinner-border-sm', 'toast', 'toast-body', 'toast-container', 'top-0', 'visually-hidden',
];

const classesIn = (css) => new Set([...css.replace(/\\./g, '').matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map((m) => m[1]));

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(jsx?|html)$/.test(entry.name) && !/\.test\./.test(entry.name) ? [path] : [];
  });
}

const distDir = 'dist/assets';
if (!existsSync(distDir)) {
  console.error('No dist/ found: run `npm run build` first.');
  process.exit(2);
}

const built = classesIn(
  readdirSync(distDir)
    .filter((name) => name.endsWith('.css'))
    .map((name) => readFileSync(join(distDir, name), 'utf8'))
    .join('\n'),
);
const full = classesIn(readFileSync('node_modules/bootstrap/dist/css/bootstrap.min.css', 'utf8'));

// Words inside quotes on lines mentioning a class. (Scanning every word would
// flag HTML tags like <h5> and prose such as "example.com".)
const STRING_LITERAL = /(["'`])((?:\\.|(?!\1)[^\\])*)\1/g;
const words = new Set(
  sourceFiles('src')
    .flatMap((file) => readFileSync(file, 'utf8').split('\n'))
    .filter((line) => /class/i.test(line))
    .flatMap((line) => [...line.matchAll(STRING_LITERAL)].flatMap((m) => m[2].replace(/\$\{[^}]*\}/g, ' ').match(/[A-Za-z][\w-]*/g) ?? [])),
);
const wanted = new Set([...words].filter((word) => full.has(word)).concat(REACT_BOOTSTRAP));

const missing = [...wanted].filter((name) => !built.has(name)).sort();
if (missing.length) {
  console.error(`Bootstrap classes used by the app but missing from src/bootstrap.scss output:\n  ${missing.join('\n  ')}`);
  console.error('\nAdd the matching partial / utility group to src/bootstrap.scss.');
  process.exit(1);
}
console.log(`Bootstrap check: ${wanted.size} classes in use, all present in the trimmed build.`);
