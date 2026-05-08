import React from 'react'

export default function DoctorList({ doctors, total, loading }) {
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
            <th>Nom</th>
            <th>Prénom</th>
            <th>Ville</th>
            <th>Département</th>
            <th>Exercice</th>
            <th>Contact</th>
          </tr>
        </thead>
        <tbody>
          {doctors.length === 0 ? (
            <tr><td colSpan="6" className="no-results">Aucun neurologue trouvé</td></tr>
          ) : (
            doctors.map(doc => (
              <tr key={doc.id_ppss}>
                <td><strong>{doc.nom}</strong></td>
                <td>{doc.prenom}</td>
                <td>{doc.commune}</td>
                <td>{doc.departement}</td>
                <td>
                  <span className={`badge ${doc.mode_exercice?.toLowerCase()}`}>
                    {doc.mode_exercice === 'LIBERAL' ? '🏥 Cabinet' : 
                     doc.mode_exercice === 'HOSPITALIER' ? '🏥 Hôpital' : doc.mode_exercice}
                  </span>
                </td>
                <td>
                  {doc.tel && <span>📞 {doc.tel}</span>}
                  {doc.mail && <br /><span>✉️ {doc.mail}</span>}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}