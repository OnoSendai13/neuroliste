import React from 'react'
import { MapPin, BuildingOffice, MagnifyingGlass, Download, FunnelSimple, X, CaretDown } from '@phosphor-icons/react'

const REGION_NAMES = {
  'AuRA': 'Auvergne-Rhône-Alpes',
  'BFC': 'Bourgogne-Franche-Comté',
  'BIF': 'Bretagne',
  'Centre-Val': 'Centre-Val de Loire',
  'Corse': 'Corse',
  'Grand Est': 'Grand Est',
  'HDF': 'Hauts-de-France',
  'IDF': 'Île-de-France',
  'NAQ': 'Nouvelle-Aquitaine',
  'Occitanie': 'Occitanie',
  'PDL': 'Pays de la Loire',
  'PAC': "Provence-Alpes-Côte d'Azur",
  'Normandie': 'Normandie',
  'GP': 'Guadeloupe',
  'GF': 'Guyane',
  'RE': 'Réunion',
  'FP': 'Martinique',
  'SM': 'Saint-Martin/Saint-Barth'
}

const MODE_LABELS = {
  '': 'Tous',
  'L': 'Cabinet',
  'S': 'Salarié'
}

export default function FilterPanel({ filters, onFilterChange, onExport, onClear, hasActiveFilters }) {
  const [departements, setDepartements] = React.useState([])
  const [communes, setCommunes] = React.useState([])
  const [regions, setRegions] = React.useState([])
  const [loadingLocations, setLoadingLocations] = React.useState(false)
  const [showCommunes, setShowCommunes] = React.useState(false)

  React.useEffect(() => {
    fetchRegions()
  }, [])

  React.useEffect(() => {
    fetchDepartements()
  }, [filters.region])

  const fetchRegions = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:50000'}/api/stats`)
      const data = await res.json()
      setRegions(data.regions?.map(r => r.name) || [])
    } catch (e) {
      console.error('Erreur lors du chargement des régions:', e)
    }
  }

  const fetchDepartements = async () => {
    try {
      const url = filters.region
        ? `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:50000'}/api/locations?region=${filters.region}`
        : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:50000'}/api/locations`
      const res = await fetch(url)
      const data = await res.json()
      setDepartements(Object.keys(data.departements || {}).sort())
    } catch (e) {
      console.error('Erreur lors du chargement des départements:', e)
    }
  }

  const fetchCommunes = async (dep) => {
    if (!dep) {
      setCommunes([])
      return
    }

    setLoadingLocations(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://host.docker.internal:50000'}/api/locations?departement=${dep}`)
      const data = await res.json()
      setCommunes((data.departements?.[dep] || []).sort())
    } catch (e) {
      console.error('Erreur lors du chargement des communes:', e)
    } finally {
      setLoadingLocations(false)
    }
  }

  const updateFilter = (key, value) => {
    const nextFilters = { ...filters, [key]: value }
    if (key === 'region') {
      nextFilters.departement = ''
      nextFilters.commune = ''
    }
    if (key === 'departement') {
      nextFilters.commune = ''
    }
    onFilterChange(nextFilters)
  }

  const clearFilters = () => {
    onClear()
  }

  const activeFiltersCount = Object.entries(filters).filter(([_, value]) => value).length

  return (
    <div className="section-card animate-slide-up">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <FunnelSimple className="w-5 h-5 text-primary" weight="bold" />
            <h2 className="text-lg font-semibold">Filtres de recherche</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Affinez votre recherche par localisation ou mode d'exercice
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="btn btn-ghost btn-sm"
            >
              <X className="w-4 h-4" />
              Réinitialiser
            </button>
          )}
          <button
            onClick={onExport}
            className="btn btn-primary btn-sm"
          >
            <Download className="w-4 h-4" />
            Exporter CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-6">
        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center gap-2">
            <MapPin className="w-4 h-4 text-muted-foreground" />
            Région
          </label>
          <select
            value={filters.region}
            onChange={(e) => updateFilter('region', e.target.value)}
            className="select"
          >
            <option value="">Toutes les régions</option>
            {regions.map(r => (
              <option key={r} value={r}>{REGION_NAMES[r] || r}</option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center gap-2">
            <MapPin className="w-4 h-4 text-muted-foreground" />
            Département
          </label>
          <select
            value={filters.departement}
            onChange={(e) => {
              updateFilter('departement', e.target.value)
              fetchCommunes(e.target.value)
            }}
            className="select"
          >
            <option value="">Tous les départements</option>
            {departements.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center gap-2">
            <MagnifyingGlass className="w-4 h-4 text-muted-foreground" />
            Ville
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder="Rechercher une ville..."
              value={filters.commune}
              onChange={(e) => updateFilter('commune', e.target.value)}
              onFocus={() => setShowCommunes(true)}
              list="communes-list"
              disabled={loadingLocations || !filters.departement}
              className="input pr-10"
            />
            <button
              type="button"
              onClick={() => setShowCommunes(!showCommunes)}
              disabled={loadingLocations || !filters.departement}
              className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30"
            >
              <CaretDown className="w-4 h-4" />
            </button>
            {showCommunes && communes.length > 0 && (
              <div className="absolute z-20 left-0 right-0 top-full mt-1 max-h-60 overflow-y-auto bg-card border border-border rounded-xl shadow-elevation-2 animate-scale-in">
                {communes.map(c => (
                  <button
                    key={c}
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted/50 first:rounded-t-xl last:rounded-b-xl"
                    onClick={() => {
                      updateFilter('commune', c)
                      setShowCommunes(false)
                    }}
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
          <datalist id="communes-list">
            {communes.map(c => <option key={c} value={c} />)}
          </datalist>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center gap-2">
            <BuildingOffice className="w-4 h-4 text-muted-foreground" />
            Mode d'exercice
          </label>
          <select
            value={filters.mode_exercice || ''}
            onChange={(e) => updateFilter('mode_exercice', e.target.value)}
            className="select"
          >
            {Object.entries(MODE_LABELS).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      {activeFiltersCount > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 p-3 rounded-xl bg-muted/50 border border-border">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Filtres actifs
          </span>
          {Object.entries(filters).map(([key, value]) => {
            if (!value) return null
            const label = key === 'region' ? REGION_NAMES[value] || value :
                          key === 'departement' ? `Dép. ${value}` :
                          key === 'commune' ? `Ville: ${value}` :
                          key === 'mode_exercice' ? MODE_LABELS[value] || value : value
            return (
              <span key={key} className="badge badge-primary">
                {label}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}