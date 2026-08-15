/**
 * Database migration system for Neuroliste.
 * 
 * Usage:
 * - Place migration files in electron/migrations/ as 001_description.js, 002_*.js, etc.
 * - Each migration exports: { version: number, up: async (db) => {...}, down: async (db) => {...} }
 * - Run: node electron/migrations.js
 */

const fs = require('fs');
const path = require('path');
const sqlite3 = require('better-sqlite3');

const MIGRATIONS_DIR = path.join(__dirname, 'migrations');
const META_TABLE = 'schema_migrations';

function getDbPath(customPath) {
  // This should match electron/main.js getDbPath()
  if (customPath) {
    return path.join(customPath, 'neurologues.db');
  }
  try {
    const { app } = require('electron');
    const userDataPath = app.getPath('userData');
    return path.join(userDataPath, 'neurologues.db');
  } catch {
    // Fallback for CLI usage outside Electron
    const fallbackPath = process.env.NEUROLISTE_DB_PATH || path.join(process.cwd(), 'backend', 'data', 'neurologues.db');
    return fallbackPath;
  }
}

function ensureMetaTable(db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS ${META_TABLE} (
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      applied_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
}

function getAppliedMigrations(db) {
  ensureMetaTable(db);
  const rows = db.prepare(`SELECT version FROM ${META_TABLE} ORDER BY version`).all();
  return new Set(rows.map(r => r.version));
}

function loadMigrations() {
  if (!fs.existsSync(MIGRATIONS_DIR)) {
    fs.mkdirSync(MIGRATIONS_DIR, { recursive: true });
    return [];
  }
  
  const files = fs.readdirSync(MIGRATIONS_DIR)
    .filter(f => f.endsWith('.js'))
    .sort();
  
  return files.map(file => {
    const migration = require(path.join(MIGRATIONS_DIR, file));
    const version = parseInt(file.split('_')[0], 10);
    return { version, file, ...migration };
  });
}

function runMigrations(customPath) {
  const dbPath = getDbPath(customPath);

  if (!fs.existsSync(dbPath)) {
    console.error(`Database not found at: ${dbPath}`);
    console.error('Run the app first to initialize the database.');
    process.exit(1);
  }

  const db = new sqlite3(dbPath);
  const applied = getAppliedMigrations(db);
  const migrations = loadMigrations();

  const pending = migrations.filter(m => !applied.has(m.version));

  if (pending.length === 0) {
    console.log('No pending migrations.');
    return;
  }

  console.log(`Found ${pending.length} pending migration(s):`);
  pending.forEach(m => console.log(`  ${m.version}: ${m.file}`));

  for (const migration of pending) {
    console.log(`\nApplying migration ${migration.version}...`);

    const transaction = db.transaction(() => {
      migration.up(db);
      db.prepare(`INSERT INTO ${META_TABLE} (version, name) VALUES (?, ?)`)
        .run(migration.version, migration.file);
    });

    try {
      transaction();
      console.log(`  ✓ Applied ${migration.version}`);
    } catch (err) {
      console.error(`  ✗ Failed: ${err.message}`);
      throw err;
    }
  }

  console.log('\nAll migrations applied successfully.');
  db.close();
}

function rollbackMigration(version, customPath) {
  const dbPath = getDbPath(customPath);
  const db = new sqlite3(dbPath);
  const applied = getAppliedMigrations(db);
  const migrations = loadMigrations();

  const target = migrations.find(m => m.version === version);
  if (!target) {
    console.error(`Migration ${version} not found.`);
    process.exit(1);
  }

  if (!applied.has(version)) {
    console.error(`Migration ${version} not applied.`);
    process.exit(1);
  }

  console.log(`Rolling back migration ${version}...`);

  const transaction = db.transaction(() => {
    target.down(db);
    db.prepare(`DELETE FROM ${META_TABLE} WHERE version = ?`).run(version);
  });

  try {
    transaction();
    console.log(`  ✓ Rolled back ${version}`);
  } catch (err) {
    console.error(`  ✗ Failed: ${err.message}`);
    throw err;
  }

  db.close();
}

// CLI
const args = process.argv.slice(2);
const customPath = args.includes('--db-path') ? args[args.indexOf('--db-path') + 1] : undefined;

if (args[0] === 'rollback') {
  const version = parseInt(args[1], 10);
  if (isNaN(version)) {
    console.error('Usage: node migrations.js rollback <version> [--db-path /path/to/db]');
    process.exit(1);
  }
  rollbackMigration(version, customPath);
} else {
  runMigrations(customPath);
}

module.exports = { runMigrations, rollbackMigration, getDbPath };