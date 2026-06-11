import React from 'react'

export default function Pagination({ currentPage, total, limit, onPageChange }) {
  const totalPages = Math.ceil(total / limit)
  
  if (totalPages <= 1) return null

  const pages = []
  const maxVisible = 5
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
  let end = Math.min(totalPages, start + maxVisible - 1)
  
  if (end - start < maxVisible - 1) {
    start = Math.max(1, end - maxVisible + 1)
  }

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return (
    <div className="pagination">
      <button 
        onClick={() => onPageChange(1)}
        disabled={currentPage === 1}
      >
        « Début
      </button>
      
      <button 
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
      >
        ‹ Préc.
      </button>

      {start > 1 && (
        <>
          <button onClick={() => onPageChange(1)}>1</button>
          {start > 2 && <span>...</span>}
        </>
      )}

      {pages.map(p => (
        <button
          key={p}
          className={p === currentPage ? 'active' : ''}
          onClick={() => onPageChange(p)}
        >
          {p}
        </button>
      ))}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span>...</span>}
          <button onClick={() => onPageChange(totalPages)}>
            {totalPages}
          </button>
        </>
      )}

      <button 
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
      >
        Suiv. ›
      </button>
      
      <button 
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage === totalPages}
      >
        Fin »
      </button>
    </div>
  )
}