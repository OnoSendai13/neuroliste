import React, { useState } from 'react'

export default function DoctorList({ doctors, total, loading, sortField, sortDir, onSort }) {
  const handleSort = (field) => {
    onSort?.(field)
  }

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="sort-indicator">⇅</span>
    return <span className="sort-indicator">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  if (loading) {
    return <div className="loading">Chargement...</div>
  }

  return (
    <div className="doctor-list">
      <div className="list-header">
        <h2>{total} neurologue{total > 1 ? 's' : ''}</h2>
      </div>
      
      <table>
        <thead>
          <tr>
            <th onClick={() => handleSort('nom')} className="sortable">Nom <SortIcon field="nom" /></th>
            <th onClick={() => handleSort('prenom')} className="sortable">Prénom <SortIcon field="prenom" /></th>
            <th onClick={() => handleSort('commune')} className="sortable">Ville <SortIcon field="commune" /></th>
            <th onClick={() => handleSort('departement')} className="sortable">Département <SortIcon field="departement" /></th>
            <th onClick={() => handleSort('mode_exercice')} className="sortable">Exercice <SortIcon field="mode_exercice" /></th>
            <th>Structure</th>
            <th>Email</th>
            <th>Contact</th>
          </tr>
        </thead>
        <tbody>
          {doctors.length === 0 ? (
            <tr><td colSpan="8" className="no-results">Aucun neurologue trouvé</td></tr>
          ) : (
            doctors.map(doc => (
              <tr key={doc.id_ppss}>
                <td><strong>{doc.nom}</strong></td>
                <td>{doc.prenom}</td>
                <td>{doc.commune}</td>
                <td>{doc.departement}</td>
                <td>
                  <span className={`badge ${doc.mode_exercice?.toLowerCase()}`}>
                    {doc.mode_exercice === 'L' ? 'Cabinet' : 
                     doc.mode_exercice === 'S' ? 'Salarié' : 
                     doc.mode_exercice === 'H' ? 'Hospitalier' : 
                     doc.mode_exercice || '-'}
                  </span>
                </td>
                <td>{doc.structure ? doc.structure.split(' - ')[0] : ''}</td>
                <td>{doc.mail}</td>
                <td>{doc.tel}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}