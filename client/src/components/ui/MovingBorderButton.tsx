import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface MovingBorderButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
}

export function MovingBorderButton({ children, className = '', ...rest }: MovingBorderButtonProps) {
  return (
    <button className={`moving-border-btn ${className}`.trim()} {...rest}>
      <span>{children}</span>
    </button>
  )
}
