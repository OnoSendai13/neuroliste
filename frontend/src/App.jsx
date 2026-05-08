import React from 'react'
import Filters from './components/Filters'
import DoctorList from './components/DoctorList'
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

  React.useEffect(() => {
    fetchDoctors()
  }, [filters])

  const fetchDoctors = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.append(k, v)
    })
    
    const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/doctors?${params}`)
    const data = await res.json()
    setDoctors(data.doctors)
    setTotal(data.total)
    setLoading(false)
  }

  const handleLoadData = async () => {
    setLoadingData(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/load-data`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.status === 'success') {
        alert(`Data loaded: ${data.output || ''}`)
        fetchDoctors()
      } else {
        alert(`Error: ${data.message || JSON.stringify(data)}`)
      }
    } catch (e) {
      alert(`Error: ${e.message}`)
    }
    setLoadingData(false)
  }

  const handleExport = async () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.append(k, v)
    })
    
    const res = await fetch(`${import.meta.env.VITE_API_URL}/api/export?${params}`)
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
          <span style={{marginLeft: '1rem', color: '#666'}}>
            {total} neurologue{total > 1 ? 's' : ''} found
          </span>
        </div>
        
        <Filters 
          filters={filters} 
          onFilterChange={setFilters}
          onExport={handleExport}
        />
        
        <DoctorList 
          doctors={doctors}
          total={total}
          loading={loading}
        />
      </main>
    </div>
  )
}

export default App