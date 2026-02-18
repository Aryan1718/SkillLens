import { MovingBorderButton } from '../ui/MovingBorderButton'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) {
    return null
  }

  return (
    <nav className="pagination" aria-label="Skills pagination">
      <MovingBorderButton
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
      >
        Previous
      </MovingBorderButton>
      <span>
        Page {page} of {totalPages}
      </span>
      <MovingBorderButton
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="Next page"
      >
        Next
      </MovingBorderButton>
    </nav>
  )
}
