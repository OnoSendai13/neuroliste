import React from 'react'
import { CaretLeft, CaretRight, DotsThree } from '@phosphor-icons/react'

export default function Pagination({ currentPage, total, limit, onPageChange }) {
  const totalPages = Math.ceil(total / limit)

  if (totalPages <= 1) return null

  const getPageNumbers = () => {
    const pages = []
    const maxVisible = 5

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
      return pages
    }

    if (currentPage <= 3) {
      for (let i = 1; i <= 4; i++) {
        pages.push(i)
      }
      pages.push('ellipsis')
      pages.push(totalPages)
    } else if (currentPage >= totalPages - 2) {
      pages.push(1)
      pages.push('ellipsis')
      for (let i = totalPages - 3; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)
      pages.push('ellipsis')
      for (let i = currentPage - 1; i <= currentPage + 1; i++) {
        pages.push(i)
      }
      pages.push('ellipsis')
      pages.push(totalPages)
    }

    return pages
  }

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-4">
      <p className="text-sm text-muted-foreground">
        Page {currentPage} sur {totalPages}
      </p>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage === 1}
          className="btn btn-secondary btn-sm"
        >
          <CaretLeft className="w-4 h-4" />
        </button>

        {getPageNumbers().map((page, index) => (
          page === 'ellipsis' ? (
            <span key={`ellipsis-${index}`} className="px-3 py-2 text-muted-foreground">
              <DotsThree className="w-5 h-5" />
            </span>
          ) : (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={`
                btn btn-sm min-w-[2.5rem]
                ${currentPage === page ? 'btn-primary' : 'btn-secondary'}
              `}
            >
              {page}
            </button>
          )
        ))}

        <button
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage === totalPages}
          className="btn btn-secondary btn-sm"
        >
          <CaretRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}