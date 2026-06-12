import React from 'react'
import { Brain, Database, ArrowsClockwise, Eye, EyeSlash, Pulse, Users, MapPin, ChartBar, Download } from '@phosphor-icons/react'
import FilterPanel from './components/FilterPanel'
import DoctorTable from './components/DoctorTable'
import Pagination from './components/Pagination'
import StatsDashboard from './components/StatsDashboard'
import ThemeToggle from './components/ThemeToggle'
import './index.css'

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
  const [theme, setTheme] = React.useState('system')
  const [lastExtraction, setLastExtraction] = React.useState(null)
  const [lastImport, setLastImport] = React.useState(null)

  React.useEffect(() => {
    fetchDoctors(1)
  }, [filters, sortField, sortDir])

  React.useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')
    
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }
  }, [theme])

  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:50000'

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
    
    try {
      const res = await fetch(`${apiUrl}/api/doctors?${params}`)
      const data = await res.json()
      setDoctors(data.doctors || [])
      setTotal(data.total || 0)
      setCurrentPage(page)
      
      // Fetch last extraction date
      try {
        const statsRes = await fetch(`${apiUrl}/api/stats`)
        const statsData = await statsRes.json()
        setLastExtraction(statsData.last_extraction)
        setLastImport(statsData.last_import)
      } catch (e) {
        console.error('Erreur lors du chargement des dates:', e)
      }
    } catch (e) {
      console.error('Erreur lors du chargement:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (field) => {
    setSortField(field)
    setSortDir(prev => sortField === field && prev === 'asc' ? 'desc' : 'asc')
  }

  const handleLoadData = async () => {
    setLoadingData(true)
    try {
      const res = await fetch(`${apiUrl}/api/load-data`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.status === 'success') {
        alert('Données chargées avec succès')
        fetchDoctors(1)
      } else {
        alert('Erreur: ' + (data.message || JSON.stringify(data)))
      }
    } catch (e) {
      alert('Erreur: ' + e.message)
    }
    setLoadingData(false)
  }

  const handleExport = async () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.append(k, v)
    })
    
    try {
      const res = await fetch(`${apiUrl}/api/export?${params}`)
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `neurologues_${filters.departement || 'all'}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Erreur lors de l\'export:', e)
    }
  }

  const hasActiveFilters = Object.values(filters).some(Boolean)

  const activeFiltersCount = Object.entries(filters).filter(([_, value]) => value).length

  return (
    <div className="app-shell">
      <ThemeToggle theme={theme} setTheme={setTheme} />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero */}
        <header className="relative overflow-hidden rounded-3xl glass-panel p-8 mb-8">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-blue-500/10" />
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary/20 rounded-full blur-3xl opacity-50" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl opacity-50" />
          
          <div className="relative z-10">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              <div className="space-y-4 max-w-2xl">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                    <Brain className="w-6 h-6 text-primary" weight="bold" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-primary uppercase tracking-wider">Annuaire RPPS</p>
                    <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-balance">
                      Neurologues de France
                    </h1>
                  </div>
                </div>
                <p className="text-lg text-muted-foreground leading-relaxed max-w-xl">
                  Explorez la cartographie nationale des neurologues avec des données actualisées,
                  des filtres précis et des statistiques détaillées par territoire.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  onClick={handleLoadData}
                  disabled={loadingData}
                  className="btn btn-secondary btn-lg"
                >
                  <ArrowsClockwise className={`w-5 h-5 ${loadingData ? 'animate-spin' : ''}`} />
                  {loadingData ? 'Chargement...' : 'Actualiser les données'}
                </button>
                <button
                  onClick={() => setShowStats(!showStats)}
                  className="btn btn-primary btn-lg"
                >
                  {showStats ? (
                    <>
                      <EyeSlash className="w-5 h-5" />
                      Masquer les stats
                    </>
                  ) : (
                    <>
                      <Eye className="w-5 h-5" />
                      Afficher les stats
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
              <div className="glass-panel rounded-2xl p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Users className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{total.toLocaleString('fr-FR')}</p>
                    <p className="text-sm text-muted-foreground">neurologues</p>
                  </div>
                </div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                    <MapPin className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{activeFiltersCount}</p>
                    <p className="text-sm text-muted-foreground">filtres actifs</p>
                  </div>
                </div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                    <ChartBar className="w-5 h-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{showStats ? 'Oui' : 'Non'}</p>
                    <p className="text-sm text-muted-foreground">statistiques</p>
                  </div>
                </div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                    <ChartBar className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-lg font-bold">
                      {lastImport ? new Date(lastImport).toLocaleDateString('fr-FR') : '-'}
                    </p>
                    <p className="text-sm text-muted-foreground">dernier import</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="space-y-6">
          {showStats && (
            <StatsDashboard apiUrl={apiUrl} filters={filters} />
          )}

          <FilterPanel
            filters={filters}
            onFilterChange={setFilters}
            onExport={handleExport}
            onClear={() => setFilters({
              region: '',
              departement: '',
              commune: '',
              mode_exercice: ''
            })}
            hasActiveFilters={hasActiveFilters}
          />

          <section className="section-card">
            <DoctorTable
              doctors={doctors}
              total={total}
              loading={loading}
              sortField={sortField}
              sortDir={sortDir}
              onSort={handleSort}
            />
          </section>

          <section className="section-card">
            <Pagination
              currentPage={currentPage}
              total={total}
              limit={limit}
              onPageChange={fetchDoctors}
            />
          </section>
        </main>

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-muted-foreground">
          <p>Données RPPS - Mise à jour automatique depuis data.gouv.fr</p>
        </footer>
      </div>
    </div>
  )
}

export default App