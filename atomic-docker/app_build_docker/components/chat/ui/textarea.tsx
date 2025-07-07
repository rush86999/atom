import * as React from 'react'

import { cn } from '@lib/Chat/utils'

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[60px] w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-base font-sans text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-0 focus-visible:border-sky-500 dark:focus-visible:border-sky-500 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm', // Adjusted styles for modern look, readability, and dark mode
          // Note: min-h-[60px] is often overridden by ChatInput.tsx specific styles if used there. Default min-h can be adjusted.
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = 'Textarea'

export { Textarea }