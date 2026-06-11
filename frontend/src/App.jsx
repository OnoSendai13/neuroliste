import React from 'react'
import Filters from './components/Filters'
import DoctorList from './components/DoctorList'
import Pagination from './components/Pagination'
import StatsPanel from './components/StatsPanel'
import './App.css'

function App() {
  const [filters, setFilters] = React.useState({
    region: '',
    departement: '',
    commune: '',
    mode_exercice: ''
  })
  
  const [doctors, setDoctors] = React.useState([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(false)
  const [loadingData, setLoadingData] = React.useState(false)
  const [limit] = React.useState(100)
  const [currentPage, setCurrentPage] = React.useState(1)
  const [sortField, setSortField] = React.useState(null)
  const [sortDir, setSortDir] = React.useState('asc')
  const [showStats, setShowStats] = React.useState(false)

  React.useEffect(() => {
    fetchDoctors(1)
  }, [filters, sortField, sortDir])

  const fetchDoctors = async (page = 1) => {
    page = Math.max(1, page)
    setLoading(true)
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.append(k, v)
    })
    if (sortField) {
      params.append('sort', sortField)
      params.append('order', sortDir)
    }
    params.append('skip', (page - 1) * limit)
    params.append('limit', limit)
    
    const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://host.docker.internal:50000'}/api/doctors?${params}`)
    const data = await res.json()
    setDoctors(data.doctors || [])
    setTotal(data.total || 0)
    setCurrentPage(page)
    setLoading(false)
  }

  const handleSort = (field) => {
    setSortField(field)
    setSortDir(prev => sortField === field && prev === 'asc' ? 'desc' : 'asc')
  }

  const handleLoadData = async () => {
    setLoadingData(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://host.docker.internal:50000'}/api/load-data`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.status === 'success') {
        alert('Data loaded')
        fetchDoctors(1)
      } else {
        alert('Error: ' + (data.message || JSON.stringify(data)))
      }
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setLoadingData(false)
  }

  const handleExport = async () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.append(k, v)
    })
    
    const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://host.docker.internal:50000'}/api/export?${params}`)
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `neurologues_${filters.departement || 'all'}.csv`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="app">
      <header>
        <h1>RPPS Neurologues</h1>
        <p>Annuaire des neurologues francais</p>
      </header>
      
      <main>
        <div style={{marginBottom: '1rem'}}>
          <button onClick={handleLoadData} disabled={loadingData}>
            {loadingData ? 'Loading...' : 'Load RPPS Data'}
          </button>
          <button onClick={() => setShowStats(!showStats)} style={{marginLeft: '0.5rem'}}>
            {showStats ? 'Masquer stats' : 'Afficher stats'}
          </button>
          <span style={{marginLeft: '1rem', color: '#666'}}>
            {total} neurologue{total > 1 ? 's' : ''} found
          </span>
        </div>
        
        {showStats && <StatsPanel apiUrl={import.meta.env.VITE_API_URL || 'http://127.0.0.1:50000'} filters={filters} />}
        
        <Filters 
          filters={filters}
          onFilterChange={setFilters}
          onExport={handleExport}
        />
        
        <div className="table-container">
          <DoctorList 
            doctors={doctors}
            total={total}
            loading={loading}
            sortField={sortField}
            sortDir={sortDir}
            onSort={handleSort}
          />
          
          {total > limit && (
            <Pagination
              currentPage={currentPage}
              total={total}
              limit={limit}
              onPageChange={fetchDoctors}
            />
          )}
        </div>
      </main>
    </div>
  )
}

export default App
