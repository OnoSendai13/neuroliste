import React from 'react'

export default function Filters({ filters, onFilterChange, onExport }) {
  const [departements, setDepartements] = React.useState([])
  const [communes, setCommunes] = React.useState([])
  const [loadingLocations, setLoadingLocations] = React.useState(false)

  React.useEffect(() => {
    fetchDepartements()
  }, [])

  const fetchDepartements = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://host.docker.internal:50000'}/api/locations`)
      const data = await res.json()
      setDepartements(Object.keys(data.departements || {}))
    } catch (e) {
      console.error(e)
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
      setCommunes(data.departements?.[dep] || [])
    } catch (e) {
      console.error(e)
    }
    setLoadingLocations(false)
  }

  return (
    <div className="filters">
      <div className="filter-row">
        <div className="filter-group">
          <label>Département</label>
          <select 
            value={filters.departement}
            onChange={(e) => {
              onFilterChange({...filters, departement: e.target.value, commune: ''})
              fetchCommunes(e.target.value)
            }}
          >
            <option value="">Tous les départements</option>
            {departements.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
        
        <div className="filter-group">
          <label>Ville</label>
          <input
            type="text"
            placeholder="Rechercher une ville..."
            value={filters.commune}
            onChange={(e) => onFilterChange({...filters, commune: e.target.value})}
            list="communes-list"
            disabled={loadingLocations || !filters.departement}
          />
          <datalist id="communes-list">
            {communes.map(c => <option key={c} value={c} />)}
          </datalist>
        </div>
      </div>

      <div className="filter-row">
        <div className="filter-group">
          <label>Mode d'exercice</label>
          <div className="radio-group">
            <label>
              <input
                type="radio"
                name="mode"
                value=""
                checked={!filters.mode_exercice || filters.mode_exercice === ''}
                onChange={() => onFilterChange({...filters, mode_exercice: ''})}
              />
              Tous
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                value="L"
                checked={filters.mode_exercice === 'L'}
                onChange={() => onFilterChange({...filters, mode_exercice: 'L'})}
              />
              Cabinet
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                value="S"
                checked={filters.mode_exercice === 'S'}
                onChange={() => onFilterChange({...filters, mode_exercice: 'S'})}
              />
              Salarié
            </label>
          </div>
        </div>
      </div>

      <div className="actions">
        <button onClick={onExport} className="btn-export">
          📥 Exporter CSV
        </button>
      </div>
    </div>
  )
}