/**
 * Migration 001: Add schema_version table and index optimizations.
 * This is the baseline migration for existing databases.
 */

module.exports = {
  version: 1,
  
  up: (db) => {
    // Add schema_version table if not exists (meta table is handled by migrations.js)
    db.exec(`
      CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `);
    
    // Add useful indexes for common queries
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_neurologues_departement 
      ON neurologues(departement)
    `);
    
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_neurologues_commune 
      ON neurologues(commune)
    `);
    
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_neurologues_mode_exercice 
      ON neurologues(mode_exercice)
    `);
    
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_neurologues_nom_prenom 
      ON neurologues(nom, prenom)
    `);
    
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_neurologues_region 
      ON neurologues(region)
    `);
    
    console.log('  Added indexes for departement, commune, mode_exercice, nom/prenom, region');
  },
  
  down: (db) => {
    db.exec('DROP INDEX IF EXISTS idx_neurologues_departement');
    db.exec('DROP INDEX IF EXISTS idx_neurologues_commune');
    db.exec('DROP INDEX IF EXISTS idx_neurologues_mode_exercice');
    db.exec('DROP INDEX IF EXISTS idx_neurologues_nom_prenom');
    db.exec('DROP INDEX IF EXISTS idx_neurologues_region');
    db.exec('DROP TABLE IF EXISTS schema_version');
    console.log('  Dropped indexes and schema_version table');
  }
};