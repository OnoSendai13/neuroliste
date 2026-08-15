import React from 'react'
import { WarningCircle, CheckCircle, ArrowClockwise, Database, Eye, Download, Upload, Gear, ArrowsClockwise } from '@phosphor-icons/react'

function CorrectionsPanel({ apiUrl }) {
  const [pendingEntries, setPendingEntries] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [success, setSuccess] = React.useState('')
  const [applying, setApplying] = React.useState(false)
  const [updates, setUpdates] = React.useState(null)
  const [checkingUpdates, setCheckingUpdates] = React.useState(false)

  const fetchPending = async () => {
    setLoading(true)
    setError('')
    try {
      const { corrections } = window.electronAPI
      const result = await corrections.listPending()
      if (result.error) {
        setError(result.error)
        setPendingEntries([])
      } else {
        setPendingEntries(result.entries || [])
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const promoteEntry = async (id_ppss) => {
    try {
      const { corrections } = window.electronAPI
      const result = await corrections.promoteToConfirmed(id_ppss)
      if (result.success) {
        setSuccess(`Entrée ${id_ppss} promue à confirmed`)
        fetchPending()
      } else {
        setError(result.error)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  const applyConfirmed = async () => {
    setApplying(true)
    setError('')
    setSuccess('')
    try {
      const { corrections } = window.electronAPI
      const result = await corrections.applyConfirmed()
      if (result.success) {
        setSuccess('Corrections appliquées avec succès')
        setError(result.applyErrors || '')
        fetchPending()
      } else {
        setError(result.error)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setApplying(false)
    }
  }

  const checkUpdates = async () => {
    setCheckingUpdates(true)
    try {
      const { corrections } = window.electronAPI
      const result = await corrections.checkUpdates()
      setUpdates(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setCheckingUpdates(false)
    }
  }

  const triggerLoadData = async () => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const { corrections } = window.electronAPI
      const result = await corrections.triggerLoadData()
      if (result.status === 'success') {
        setSuccess('Données RPPS rechargées')
      } else {
        setError(result.detail || result.message || 'Erreur inconnue')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    fetchPending()
    checkUpdates()
  }, [])

  const confirmedCount = pendingEntries.filter(e => e.status === 'confirmed' && e.apply_allowed === 'true').length
  const pendingCount = pendingEntries.filter(e => e.status === 'pending_review').length

  return (
    <section className="section-card">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
            <Gear className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Gestion des corrections d'adresses</h2>
            <p className="text-sm text-muted-foreground">
              {pendingEntries.length} entrées au total • {pendingCount} en attente • {confirmedCount} confirmées prêtes à appliquer
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchPending} disabled={loading} className="btn btn-secondary">
            <ArrowClockwise className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Actualiser
          </button>
          <button onClick={checkUpdates} disabled={checkingUpdates} className="btn btn-secondary">
            <ArrowClockwise className={`w-4 h-4 ${checkingUpdates ? 'animate-spin' : ''}`} />
            Vérifier MAJ
          </button>
          <button onClick={triggerLoadData} disabled={loading} className="btn btn-primary">
            <Upload className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Recharger RPPS
          </button>
        </div>
      </div>

      {updates && (
        <div className={`mb-4 rounded-xl px-4 py-3 text-sm font-medium ${updates.update_available ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' : 'bg-green-500/10 text-green-600 dark:text-green-400'}`}>
          {updates.update_available ? (
            <>
              <WarningCircle className="w-4 h-4 inline mr-2" />
              Nouvelles données RPPS disponibles ! Local: {updates.local_import_date || 'inconnu'} → Remote: {updates.remote_last_modified || 'inconnu'}
            </>
          ) : (
            <>
              <CheckCircle className="w-4 h-4 inline mr-2" />
              Données à jour (dernier import: {updates.local_import_date || 'inconnu'})
            </>
          )}
          {updates.error && <span className="ml-2 text-red-500">Erreur: {updates.error}</span>}
        </div>
      )}

      {(error || success) && (
        <div className={`mb-4 rounded-xl px-4 py-3 text-sm font-medium ${error ? 'bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-green-500/10 text-green-600 dark:text-green-400'}`}>
          {error || success}
        </div>
      )}

      {pendingEntries.length === 0 && !loading && (
        <div className="glass-panel rounded-2xl p-8 text-center">
          <Eye className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
          <p className="text-muted-foreground">Aucune correction en attente de révision</p>
        </div>
      )}

      {pendingEntries.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">ID RPPS</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Nom</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Prénom</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Commune</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Département</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Champs à corriger</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Statut</th>
                <th className="text-left p-3 font-medium text-sm uppercase tracking-wider text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingEntries.map((entry, idx) => (
                <tr key={entry.id_ppss || idx} className="border-b border-border/50 hover:bg-accent/50">
                  <td className="p-3 font-mono text-sm">{entry.id_ppss}</td>
                  <td className="p-3 font-medium">{entry.nom}</td>
                  <td className="p-3">{entry.prenom}</td>
                  <td className="p-3 text-sm text-muted-foreground">{entry.commune}</td>
                  <td className="p-3 text-sm text-muted-foreground">{entry.departement}</td>
                  <td className="p-3 text-sm font-medium text-amber-600 dark:text-amber-400">{entry.correction_fields || entry.correctionFields || 'adresse, code_postal, commune'}</td>
                  <td className="p-3">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      entry.status === 'confirmed' && entry.apply_allowed === 'true' 
                        ? 'bg-green-500/10 text-green-700 dark:text-green-400'
                        : entry.status === 'confirmed'
                          ? 'bg-blue-500/10 text-blue-700 dark:text-blue-400'
                          : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                    }`}>
                      {entry.status === 'confirmed' && entry.apply_allowed === 'true' ? '��� Confirmée' : 
                       entry.status === 'confirmed' ? 'Confirmée (apply_allowed=false)' : '��� En attente'}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      {entry.status === 'pending_review' && (
                        <button
                          onClick={() => promoteEntry(entry.id_ppss)}
                          disabled={loading}
                          className="btn btn-primary btn-sm"
                          title="Promouvoir à confirmed + apply_allowed=true"
                        >
                          <CheckCircle className="w-4 h-4" /> Confirmer
                        </button>
                      )}
                      {(entry.status === 'confirmed' && entry.apply_allowed === 'true') && (
                        <button
                          onClick={applyConfirmed}
                          disabled={applying || loading}
                          className="btn btn-secondary btn-sm"
                          title="Appliquer toutes les corrections confirmées"
                        >
                          <Database className={`w-4 h-4 ${applying ? 'animate-spin' : ''}`} /> Appliquer
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-8">
          <ArrowsClockwise className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}
    </section>
  )
}

export default CorrectionsPanel