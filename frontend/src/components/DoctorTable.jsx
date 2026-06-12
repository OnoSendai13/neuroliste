import React from 'react'
import { CaretUp, CaretDown, EnvelopeSimple, Phone, MapPin, BuildingOffice } from '@phosphor-icons/react'

const MODE_LABELS = {
  'L': 'Cabinet',
  'S': 'Salarié',
  'B': 'Mixte',
  'H': 'Hospitalier'
}

const MODE_BADGES = {
  'L': 'badge-success',
  'S': 'badge-primary',
  'B': 'badge-warning',
  'H': 'badge-danger'
}

export default function DoctorTable({ doctors, total, loading, sortField, sortDir, onSort }) {
  const handleSort = (field) => {
    onSort?.(field)
  }

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="w-4 h-4 opacity-30" />
    return sortDir === 'asc' ? (
      <CaretUp className="w-4 h-4 text-primary" />
    ) : (
      <CaretDown className="w-4 h-4 text-primary" />
    )
  }

  const getModeLabel = (code) => {
    return MODE_LABELS[code] || code || '-'
  }

  const getModeBadge = (code) => {
    return MODE_BADGES[code] || 'badge-secondary'
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="skeleton h-14" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            Résultats
            <span className="badge badge-primary">{total}</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {total} neurologue{total > 1 ? 's' : ''} correspondant à votre recherche
          </p>
        </div>
      </div>

      <div className="table-wrapper overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="table-header border-b border-border">
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('nom')}>
                <div className="flex items-center gap-2">
                  Nom
                  <SortIcon field="nom" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('prenom')}>
                <div className="flex items-center gap-2">
                  Prénom
                  <SortIcon field="prenom" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('commune')}>
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4" />
                  Ville
                  <SortIcon field="commune" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('departement')}>
                <div className="flex items-center gap-2">
                  Département
                  <SortIcon field="departement" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('region')}>
                <div className="flex items-center gap-2">
                  Région
                  <SortIcon field="region" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold cursor-pointer sortable" onClick={() => handleSort('mode_exercice')}>
                <div className="flex items-center gap-2">
                  <BuildingOffice className="w-4 h-4" />
                  Exercice
                  <SortIcon field="mode_exercice" />
                </div>
              </th>
              <th className="px-4 py-3 text-left font-semibold">Structure</th>
              <th className="px-4 py-3 text-left font-semibold">Contact</th>
            </tr>
          </thead>
          <tbody>
            {(!doctors || doctors.length === 0) ? (
              <tr>
                <td colSpan="8" className="px-4 py-12 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                      <MapPin className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium">Aucun neurologue trouvé</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Essayez de modifier vos filtres de recherche
                      </p>
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              doctors.map((doc, index) => (
                <tr key={doc.id_ppss} className={`table-row border-b border-border last:border-b-0 animate-in`} style={{ animationDelay: `${index * 30}ms` }}>
                  <td className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-sm">
                        {doc.nom?.charAt(0) || '?'}
                      </div>
                      <div>
                        <div className="font-medium">{doc.nom}</div>
                        <div className="text-xs text-muted-foreground">RPPS: {doc.numero_rpps || '-'}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">{doc.prenom}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-muted-foreground" />
                      {doc.commune}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium">{doc.departement}</td>
                  <td className="px-4 py-3">
                    <span className="badge badge-secondary">{doc.region}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${getModeBadge(doc.mode_exercice)}`}>
                      {getModeLabel(doc.mode_exercice)}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-[240px]">
                    <div className="truncate" title={doc.structure || ''}>
                      {doc.structure || '-'}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {doc.mail && (
                        <a href={`mailto:${doc.mail}`} className="btn btn-ghost btn-sm">
                          <EnvelopeSimple className="w-4 h-4" />
                        </a>
                      )}
                      {doc.tel && (
                        <a href={`tel:${doc.tel}`} className="btn btn-ghost btn-sm">
                          <Phone className="w-4 h-4" />
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}