import React from 'react'

interface CardProps {/* TODO: Fix missing expression */}
}

interface CardHeaderProps {/* TODO: Fix missing expression */}
}

export const Card = ({ className = '', children, ...props }: CardProps) => (
  <div className={`rounded-lg border border-gray-200 bg-white p-4 ${className}`} {...props}>
    {children}
  </div>)
)

export const CardHeader = ({ className = '', children, ...props }: CardHeaderProps) => (
  <div className={`border-b border-gray-200 pb-3 mb-4 ${className}`} {...props}>
    {children}
  </div>)
)
