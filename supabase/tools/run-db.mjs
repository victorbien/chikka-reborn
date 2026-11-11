// Applies the Supabase stub, all migrations and (optionally) the dev seed or the SQL tests to a
// throwaway in-process PostgreSQL (PGlite). Nothing is written to disk or sent over the network.
//
//   node run-db.mjs                 migrations only
//   node run-db.mjs --seed          migrations + development seed
//   node run-db.mjs --tests         migrations + SQL tests (run on a database WITHOUT seed data)
//   node run-db.mjs --tests --only=04   run one test file
//
// PGlite embeds a recent PostgreSQL (see the version printed at start). It is a fast local check,
// not a replacement for running the same files against Supabase's own Postgres in CI/staging.
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const supabaseDir = path.resolve(here, '..');
const withSeed = process.argv.includes('--seed');
const withTests = process.argv.includes('--tests');
const only = process.argv.find((a) => a.startsWith('--only='))?.slice('--only='.length);

if (withSeed && withTests) {
  console.error('Seed data and tests use the same usernames. Run them separately.');
  process.exit(2);
}

export function listSql(dir) {
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.sql'))
    .sort()
    .map((f) => path.join(dir, f));
}

async function applyFile(db, file) {
  const rel = path.relative(supabaseDir, file);
  try {
    await db.exec(fs.readFileSync(file, 'utf8'));
    console.log(`ok    ${rel}`);
    return true;
  } catch (error) {
    try {
      await db.exec('rollback');
    } catch {
      /* no open transaction */
    }
    console.log(`FAIL  ${rel}\n      ${error.message}`);
    return false;
  }
}

/** Builds a database with the stub and all migrations applied. Exported for the schema generator. */
export async function buildDatabase({ quiet = false } = {}) {
  const db = new PGlite();
  const log = console.log;
  if (quiet) console.log = () => {};
  try {
    const stub = path.join(supabaseDir, 'tests/support/00_supabase_stub.sql');
    if (!(await applyFile(db, stub))) throw new Error('stub failed');
    for (const file of listSql(path.join(supabaseDir, 'migrations'))) {
      if (!(await applyFile(db, file))) throw new Error(`migration failed: ${file}`);
    }
  } finally {
    console.log = log;
  }
  return db;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const db = new PGlite();
  const version = (await db.query('select version() as v')).rows[0].v.split(',')[0];
  console.log(`Database engine: ${version}\n`);

  let ok = await applyFile(db, path.join(supabaseDir, 'tests/support/00_supabase_stub.sql'));
  for (const file of listSql(path.join(supabaseDir, 'migrations'))) {
    if (!ok) break;
    ok = await applyFile(db, file);
  }
  if (ok && withSeed) {
    for (const file of listSql(path.join(supabaseDir, 'seed'))) {
      if (!ok) break;
      ok = await applyFile(db, file);
    }
  }
  if (ok && withTests) {
    const support = listSql(path.join(supabaseDir, 'tests/support')).filter((f) => !f.includes('00_supabase_stub'));
    for (const file of support) {
      if (!ok) break;
      ok = await applyFile(db, file);
    }
    if (ok) {
      let failed = 0;
      for (const file of listSql(path.join(supabaseDir, 'tests/database'))) {
        if (only && !file.includes(only)) continue;
        if (!(await applyFile(db, file))) failed += 1;
      }
      ok = failed === 0;
    }
  }
  console.log(ok ? '\nALL OK' : '\nFAILURES');
  process.exit(ok ? 0 : 1);
}
