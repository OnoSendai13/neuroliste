import React, { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const COLORS = ['#0088fe', '#00c494', '#ffab00', '#ff5252', '#ea00ff', '#7a00ff', '#00bcd4', '#ff6b6b', '#4ecdc4', '#1a535c']

export default function StatsPanel({ apiUrl, filters }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams()
    if (filters?.region) params.append('region', filters.region)
    if (filters?.departement) params.append('departement', filters.departement)
    
    fetch(`${apiUrl}/api/stats?${params}`)
      .then(r => r.json())
      .then(setStats)
      .finally(() => setLoading(false))
  }, [apiUrl, filters])

  if (loading) return <div className="stats-loading">Chargement des stats...</div>

  const modeLabels = {
    L: 'Cabinet (Libéral)',
    S: 'Salarié',
    B: 'Mixte',
    H: 'Hospitalier'
  }

  const modeData = stats?.modes?.map(m => ({
    name: modeLabels[m.name] || m.name,
    value: m.value
  })) || []

  // Top 10 types d'etablissement

  return (
    <div className="stats-panel">
      <h3>Statistiques Neurologues</h3>
      <div className="stats-grid">
        <div className="stat-box">
          <h4>Total</h4>
          <p className="stat-value">{stats?.total}</p>
        </div>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <h4>Répartition par mode d'exercice</h4>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={modeData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
              >
                {modeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h4>Top 10 départements</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats?.departements?.slice(0, 10) || []}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#0088fe" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <h4>Répartition par région</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats?.regions?.slice(0, 10) || []}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#00c494" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}