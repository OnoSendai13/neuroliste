import React, { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, AreaChart, Area } from 'recharts'
import { Brain, Users, MapPin, Pulse, ChartLineUp } from '@phosphor-icons/react'

const COLORS = ['#0d9488', '#14b8a6', '#5eead4', '#99f6e4', '#0f766e', '#115e59', '#134e4a', '#2dd4bf']

const modeLabels = {
  'Lib,indép,artis,com': 'Cabinet (Libéral)',
  'Salarié': 'Salarié',
  'Mixte': 'Mixte',
  'Hospitalier': 'Hospitalier'
}

const modeShortLabels = {
  'Lib,indép,artis,com': 'Cabinet',
  'Salarié': 'Salarié',
  'Mixte': 'Mixte',
  'Hospitalier': 'Hospitalier'
}

export default function StatsDashboard({ apiUrl, filters }) {
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

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton h-32" />
        ))}
      </div>
    )
  }

  const modeData = stats?.modes?.map(m => ({
    name: modeLabels[m.name] || m.name,
    shortName: modeShortLabels[m.name] || m.name,
    value: m.value
  })) || []

  const departementData = stats?.departements?.slice(0, 10) || []
  const regionData = stats?.regions?.slice(0, 10) || []

  const total = stats?.total || 0

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-5 h-5 text-primary" weight="bold" />
            <h2 className="text-xl font-semibold">Tableau de bord</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Statistiques en temps réel sur la répartition des neurologues
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {stats?.last_extraction && (
            <div className="badge badge-secondary">
              Extraction: {new Date(stats.last_extraction).toLocaleDateString('fr-FR')}
            </div>
          )}
          {stats?.last_import && (
            <div className="badge badge-primary">
              Import: {new Date(stats.last_import).toLocaleDateString('fr-FR')}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="metric-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-primary" />
            </div>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Total</span>
          </div>
          <p className="text-3xl font-bold">{total.toLocaleString('fr-FR')}</p>
          <p className="text-sm text-muted-foreground mt-1">neurologues référencés</p>
        </div>

        <div className="metric-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <MapPin className="w-5 h-5 text-blue-500" />
            </div>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Régions</span>
          </div>
          <p className="text-3xl font-bold">{regionData.length}</p>
          <p className="text-sm text-muted-foreground mt-1">régions actives</p>
        </div>

        <div className="metric-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <Pulse className="w-5 h-5 text-amber-500" />
            </div>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Modes</span>
          </div>
          <p className="text-3xl font-bold">{modeData.length}</p>
          <p className="text-sm text-muted-foreground mt-1">types d'exercice</p>
        </div>

        <div className="metric-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <ChartLineUp className="w-5 h-5 text-purple-500" />
            </div>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Top dép.</span>
          </div>
          <p className="text-3xl font-bold">{departementData[0]?.name || '-'}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {departementData[0]?.value ? `${departementData[0].value} neurologues` : 'aucune donnée'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="chart-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold">Répartition par mode d'exercice</h3>
              <p className="text-sm text-muted-foreground mt-1">Répartition des pratiques</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={modeData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={4}
                dataKey="value"
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {modeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => [`${value} neurologues`, 'Effectif']}
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e4e4e7',
                  background: 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(12px)',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(value) => <span className="text-sm text-muted-foreground">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold">Top 10 départements</h3>
              <p className="text-sm text-muted-foreground mt-1">Concentration territoriale</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={departementData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <XAxis
                dataKey="name"
                tick={{ fill: '#71717a', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#71717a', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => [`${value} neurologues`, 'Effectif']}
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e4e4e7',
                  background: 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(12px)',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Bar dataKey="value" fill="#0d9488" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold">Top 10 régions</h3>
              <p className="text-sm text-muted-foreground mt-1">Distribution nationale</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={regionData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <XAxis
                dataKey="name"
                tick={{ fill: '#71717a', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#71717a', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => [`${value} neurologues`, 'Effectif']}
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e4e4e7',
                  background: 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(12px)',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#0d9488"
                fill="url(#gradient)"
                strokeWidth={2}
                fillOpacity={0.3}
              />
              <defs>
                <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}