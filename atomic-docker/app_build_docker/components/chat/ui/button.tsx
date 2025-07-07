import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@lib/Chat/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 font-sans', // Added rounded-lg, focus-visible:ring-sky-500 and font-sans (system font stack will be inherited)
  {
    variants: {
      variant: {
        default:
          'bg-sky-600 text-white hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600', // Removed shadow-md
        destructive:
          'bg-red-500 text-white hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700',
        outline:
          'border border-sky-600 text-sky-600 hover:bg-sky-100 dark:border-sky-500 dark:text-sky-500 dark:hover:bg-sky-900',
        secondary:
          'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600',
        ghost: 'hover:bg-gray-100 dark:hover:bg-gray-700 shadow-none', // Removed shadow-none as it's base now
        link: 'text-sky-600 underline-offset-4 hover:underline dark:text-sky-400 shadow-none' // Removed shadow-none
      },
      size: {
        default: 'h-9 px-4 py-2', // Adjusted height for better proportions
        sm: 'h-8 rounded-md px-3',
        lg: 'h-11 rounded-lg px-8', // Adjusted rounding
        icon: 'h-9 w-9 p-0' // Adjusted height/width for icon buttons
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'default'
    }
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }), 'font-medium')} // Ensure font-medium is applied
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }