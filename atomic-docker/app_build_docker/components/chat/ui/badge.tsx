import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@lib/Chat/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold font-sans transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2', // Added font-sans, updated focus ring
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-sky-100 text-sky-700 dark:bg-sky-800 dark:text-sky-200',
        secondary:
          'border-transparent bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
        destructive:
          'border-transparent bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200',
        outline: 'text-gray-600 border-gray-300 dark:text-gray-300 dark:border-gray-600'
      }
    },
    defaultVariants: {
      variant: 'default'
    }
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }