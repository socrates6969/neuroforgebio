// ci-lint: zero-dependency GitHub Actions workflow policy (SEC-080, SEC-089).
//   1. every third-party action is pinned by a full 40-hex commit SHA with a `# vX.Y.Z` comment
//   2. `pull_request_target` is banned (fork code must never run with secrets)
//   3. top-level `permissions: contents: read` (write scopes are granted per job only)
//   4. installs/builds use lockfiles: `pnpm install --frozen-lockfile`, `npm ci`, `uv sync --locked`,
//      `cargo build|test|clippy|run|install|doc|check --locked`; `uvx` tools pinned to an exact version
//   5. no attacker-controllable `${{ inputs.* }}`, `${{ github.event.* }}` or `${{ github.head_ref }}` inside a
//      `run:` script (APP-L3): the expression is pasted into the shell before it runs; map it through `env:`
//   6. no ad-hoc JS package runner at all (`npx` with or without -y, `pnpx`, `bunx`, `pnpm dlx`, `yarn dlx`,
//      `npm exec`) (APP-L5): every JS tool comes from a lockfile install (`pnpm exec`), and every
//      `actions/checkout` step sets `persist-credentials: false`
//   7. a job that reads a secret (`secrets.*` other than GITHUB_TOKEN) declares `environment:` (APP-L4), so the
//      owner-created environment's required reviewers gate it; exceptions only via SECRET_JOB_EXCEPTIONS,
//      each with a reason and an expiry date after which the lint fails
// The workflow trigger rule (workflow_dispatch only) lives in tools/repo-guard.
// Line-based on purpose: `run: |` blocks are scanned line by line, comments are ignored.

const SHA_RE = /^[0-9a-f]{40}$/;
const VERSION_COMMENT_RE = /#\s*v?\d+(\.\d+){1,3}\b/;

/** Strip a trailing YAML comment (outside quotes, good enough for workflow files). */
function stripComment(line) {
  let q = null;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) {
      if (c === q) q = null;
    } else if (c === '"' || c === "'") q = c;
    else if (c === '#' && (i === 0 || /\s/.test(line[i - 1]))) return line.slice(0, i);
  }
  return line;
}

/** Check one `uses:` value; returns an error string or null. */
export function checkUses(value, comment) {
  const v = value.replace(/^["']|["']$/g, '').trim();
  if (v.startsWith('./')) return null; // local action in this repo
  if (v.startsWith('docker://')) {
    return /@sha256:[0-9a-f]{64}$/.test(v) ? null : `docker action not pinned by digest: ${v}`;
  }
  const at = v.lastIndexOf('@');
  if (at < 0) return `action without a ref: ${v}`;
  const ref = v.slice(at + 1);
  if (!SHA_RE.test(ref)) return `action not pinned by full commit SHA: ${v}`;
  if (!VERSION_COMMENT_RE.test(comment || ''))
    return `SHA-pinned action lacks a "# vX.Y.Z" comment: ${v}`;
  return null;
}

// Install/build commands that must use the lockfile. Each rule: match -> required flag (regex).
const LOCK_RULES = [
  {
    name: 'pnpm install',
    match: /\bpnpm\s+(?:-[^\s]+\s+)*(?:install|i)\b/,
    ok: /--frozen-lockfile\b/,
    msg: '`pnpm install` without --frozen-lockfile',
  },
  {
    name: 'pnpm add/update',
    match: /\bpnpm\s+(?:add|update|up|upgrade)\b/,
    ok: /$^/,
    msg: '`pnpm add/update` in CI changes the lockfile',
  },
  {
    name: 'npm install',
    match: /\bnpm\s+(?:install|i|add)\b/,
    ok: /$^/,
    msg: '`npm install` in CI; use `npm ci` or pnpm --frozen-lockfile',
  },
  {
    name: 'yarn install',
    match: /\byarn(?:\s+install)?\s*$/,
    ok: /--frozen-lockfile|--immutable/,
    msg: '`yarn install` without --immutable',
  },
  {
    name: 'uv sync',
    match: /\buv\s+sync\b/,
    ok: /--locked\b|--frozen\b/,
    msg: '`uv sync` without --locked',
  },
  {
    name: 'uv pip install',
    match: /\buv\s+pip\s+install\b/,
    ok: /--require-hashes\b/,
    msg: '`uv pip install` without --require-hashes (use `uv sync --locked`)',
  },
  {
    name: 'pip install',
    match: /(?:^|[\s;&|])(?:python3?\s+-m\s+)?pip3?\s+install\b/,
    ok: /--require-hashes\b/,
    msg: '`pip install` without --require-hashes (use `uv sync --locked`)',
  },
  {
    name: 'cargo',
    match: /\bcargo\s+(?:\+\S+\s+)?(?:build|test|clippy|run|install|doc|check|bench)\b/,
    ok: /--locked\b|--frozen\b/,
    msg: '`cargo build/test/...` without --locked',
  },
];

// Python ad-hoc tools must pin an exact version: `uvx pkg@1.2.3` / `uvx pkg==1.2.3`. (JS ad-hoc runners
// such as npx are banned outright: rule 6, adHocRunner.)
const EXACT_PY = /^[A-Za-z0-9_.-]+(?:==|@)\d+(?:\.\d+){1,3}$/;

export function checkRunLine(line) {
  const errs = [];
  for (const r of LOCK_RULES) if (r.match.test(line) && !r.ok.test(line)) errs.push(r.msg);
  const uvx = /\buvx\s+((?:--?[^\s]+\s+)*)(\S+)/.exec(line);
  if (uvx && !EXACT_PY.test(uvx[2]))
    errs.push(`uvx tool not pinned to an exact version: ${uvx[2]}`);
  return errs;
}

// Expressions whose value a dispatcher or event author controls (APP-L3). Allowed in `env:`, never in `run:`.
const RUN_EXPR_RE = /\$\{\{\s*(inputs\.[\w-]+|github\.event\.[\w.-]+|github\.head_ref)/g;

/** Return the untrusted expressions used on one line of a `run:` script. */
export function runExpressions(text) {
  return [...text.matchAll(RUN_EXPR_RE)].map((m) => m[1]);
}

// APP-L5 (nfb-security, lead): any ad-hoc JS package runner can fetch and run a package outside the lockfile,
// with or without -y (npx falls back to the registry when the bin is not installed). `pnpm exec` only runs
// bins already installed from a lockfile, so it stays allowed.
const AD_HOC_RUNNER_RE = /(?:^|[\s;&|(`])(npx|pnpx|bunx|pnpm\s+dlx|yarn\s+dlx|npm\s+exec)(?=\s|$)/;

/** APP-L5: the ad-hoc package runner used on this line (`npx`, `pnpm dlx`, ...), or null. */
export function adHocRunner(line) {
  const m = AD_HOC_RUNNER_RE.exec(line);
  return m ? m[1].replace(/\s+/g, ' ') : null;
}

/** APP-L5: does the `actions/checkout` step whose `uses:` is on line i set `persist-credentials: false`? */
function checkoutDropsCredentials(lines, i) {
  const col = (l) => l.search(/\S/);
  let start = i;
  if (!/^\s*-\s/.test(lines[i])) {
    const usesCol = col(lines[i]);
    while (start > 0 && !(/^\s*-\s/.test(lines[start]) && col(lines[start]) < usesCol)) start--;
  }
  const dashCol = col(lines[start]);
  for (let j = start; j < lines.length; j++) {
    const c = stripComment(lines[j]);
    if (j > start && c.trim() && col(c) <= dashCol) break;
    if (/^\s*(?:-\s+)?persist-credentials\s*:\s*false\s*$/.test(c)) return true;
  }
  return false;
}

// APP-L4 (nfb-security, 2026-09-27): existing secret-bearing jobs that wait for owner-created GitHub
// environments. Each entry expires; after `expires` the job fails the lint again. Adding or extending an
// entry needs a security review (CODEOWNERS).
export const SECRET_JOB_EXCEPTIONS = [
  {
    workflow: 'multiverse-study.yml',
    job: 'study',
    reason: 'APP-L4, waiting on owner environments (NF_STUDY_API_TOKEN)',
    expires: '2026-10-31',
  },
  {
    workflow: 'sdk-wheels.yml',
    job: 'docs-snippets',
    reason: 'APP-L4, waiting on owner environments (NF_DOCS_STAGING_TOKEN; M4 workflow)',
    expires: '2026-10-31',
  },
];

const SECRET_RE = /\$\{\{[^}]*\bsecrets\.(?!GITHUB_TOKEN\b)[\w-]+/;

/** APP-L4: problems for jobs that use a secret without `environment:` (see SECRET_JOB_EXCEPTIONS). */
export function secretJobProblems(
  lines,
  { file = '', today = new Date().toISOString().slice(0, 10) } = {},
) {
  const problems = [];
  const workflow = file.replace(/\\/g, '/').split('/').pop();
  let inJobs = false;
  let job = null; // {name, line, secretLine, hasEnv}
  const close = () => {
    if (!job || !job.secretLine || job.hasEnv) return (job = null);
    const ex = SECRET_JOB_EXCEPTIONS.find((e) => e.workflow === workflow && e.job === job.name);
    if (ex && today <= ex.expires) return (job = null);
    problems.push({
      line: job.secretLine,
      rule: 'secret-environment',
      detail: ex
        ? `job "${job.name}": exception "${ex.reason}" expired on ${ex.expires}; declare environment: with required reviewers`
        : `job "${job.name}" uses a secret without \`environment:\` (APP-L4); add an environment with required reviewers`,
    });
    job = null;
  };
  lines.forEach((raw, i) => {
    const code = stripComment(raw);
    if (!code.trim()) return;
    if (/^\S/.test(code)) {
      close();
      inJobs = /^jobs\s*:\s*$/.test(code);
      return;
    }
    if (!inJobs) return;
    const jk = /^ {2}([\w-]+)\s*:\s*$/.exec(code);
    if (jk) {
      close();
      job = { name: jk[1], line: i + 1, secretLine: 0, hasEnv: false };
      return;
    }
    if (!job) return;
    if (/^ {4}environment\s*:/.test(code)) job.hasEnv = true;
    if (!job.secretLine && SECRET_RE.test(code)) job.secretLine = i + 1;
  });
  close();
  return problems;
}

/** Lint one workflow file's text. Returns [{line, rule, detail}]. */
export function lintWorkflow(yaml, opts = {}) {
  const problems = [];
  const lines = yaml.replace(/\r\n/g, '\n').split('\n');
  let topPermissions = null; // {line, value, children: []}
  let runCol = -1; // column of the `run:` key whose script body continues on the following lines
  const flagRun = (text, n) => {
    for (const e of runExpressions(text))
      problems.push({
        line: n,
        rule: 'run-expression',
        detail: `\`\${{ ${e} }}\` inside run: (script injection); pass it via env: and quote "$VAR"`,
      });
  };
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const code = stripComment(raw);
    const comment = raw.slice(code.length);
    const n = i + 1;
    if (runCol >= 0) {
      // Script body (block scalar or plain continuation): every line indented deeper than the key.
      if (!raw.trim() || raw.search(/\S/) > runCol) {
        flagRun(raw, n);
      } else runCol = -1;
    }
    if (!code.trim()) continue;
    const runKey = /^(\s*(?:-\s+)?)run\s*:(.*)$/.exec(code);
    if (runKey) {
      runCol = runKey[1].length;
      flagRun(runKey[2], n);
    }
    if (/\bpull_request_target\b/.test(code))
      problems.push({
        line: n,
        rule: 'pull-request-target',
        detail: '`pull_request_target` is banned',
      });
    const uses = /^\s*(?:-\s+)?uses\s*:\s*(\S+)\s*$/.exec(code);
    if (uses) {
      const e = checkUses(uses[1], comment);
      if (e) problems.push({ line: n, rule: 'action-pin', detail: e });
      if (/^["']?actions\/checkout@/.test(uses[1]) && !checkoutDropsCredentials(lines, i))
        problems.push({
          line: n,
          rule: 'checkout-credentials',
          detail:
            'actions/checkout without `with: persist-credentials: false` leaves the token in .git/config',
        });
    }
    for (const e of checkRunLine(code))
      problems.push({ line: n, rule: 'frozen-install', detail: e });
    const runner = adHocRunner(code);
    if (runner)
      problems.push({
        line: n,
        rule: 'ad-hoc-runner',
        detail: `\`${runner}\` can run a package outside the lockfile; install it from a lockfile and use \`pnpm exec\` or its node_modules/.bin path`,
      });
    const perm = /^permissions\s*:\s*(.*)$/.exec(code);
    if (perm) {
      topPermissions = { line: n, value: perm[1].trim(), children: [] };
      for (let j = i + 1; j < lines.length && /^\s+\S|^\s*$/.test(lines[j]); j++) {
        const c = stripComment(lines[j]).trim();
        if (c) topPermissions.children.push(c.replace(/\s+/g, ' '));
      }
    }
  }
  if (!topPermissions) {
    problems.push({
      line: 1,
      rule: 'permissions',
      detail: 'missing top-level `permissions: contents: read`',
    });
  } else {
    const inline = topPermissions.value.replace(/\s+/g, ' ');
    const ok =
      (inline === '' &&
        topPermissions.children.length === 1 &&
        topPermissions.children[0] === 'contents: read') ||
      inline === '{ contents: read }' ||
      inline === '{contents: read}' ||
      inline === '{}';
    if (!ok)
      problems.push({
        line: topPermissions.line,
        rule: 'permissions',
        detail: 'top-level permissions must be exactly `contents: read` (grant writes per job)',
      });
  }
  problems.push(...secretJobProblems(lines, opts));
  return problems;
}
