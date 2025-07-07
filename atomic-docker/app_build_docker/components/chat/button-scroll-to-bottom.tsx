'use client'

import * as React from 'react'
import { cn } from '@lib/Chat/utils'
import { useAtBottom } from '@lib/Chat/hooks/use-at-bottom'
import { Button, type ButtonProps } from '@components/chat/ui/button'
import { IconArrowDown } from '@components/chat/ui/icons'

export function ButtonScrollToBottom({ className, ...props }: ButtonProps) {
  const isAtBottom = useAtBottom(100) // Added offset to hide button a bit earlier

  // Determine the scroll target. If inside ScrollContainer, it should scroll that specific container.
  // For now, this button globally scrolls the window. If ScrollContainer's outerDiv needs to be scrolled,
  // this button might need access to that specific element's ref, perhaps via context or props.
  // For simplicity, keeping window scroll, but this is a point of potential improvement for nested scrollables.
  const handleScrollToBottom = () => {
    // Preferentially scroll a specific chat container if one is identifiable,
    // otherwise, fall back to window scroll. This is a conceptual improvement.
    // For now, sticking to window.scrollTo as per original.
    const chatScrollContainer = document.querySelector('[data-chat-scroll-container]'); // Example selector
    if (chatScrollContainer) {
        chatScrollContainer.scrollTo({
            top: chatScrollContainer.scrollHeight,
            behavior: 'smooth'
        });
    } else {
        window.scrollTo({
            top: document.body.scrollHeight, // Changed from offsetHeight to scrollHeight for full scroll
            behavior: 'smooth'
        });
    }
  };

  return (
    <Button
      variant="outline"
      size="icon"
      className={cn(
        'absolute right-4 bottom-24 z-20 md:bottom-28', // Adjusted position to be above ChatInput more reliably, increased z-index
        'bg-white dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600', // Explicit background and hover
        'border-gray-300 dark:border-gray-500', // Explicit border color for outline
        'text-gray-600 dark:text-gray-300', // Explicit text/icon color
        'shadow-md rounded-full transition-opacity duration-300 focus:ring-sky-500', // Ensure focus ring matches theme
        isAtBottom ? 'opacity-0 pointer-events-none' : 'opacity-100', // Added pointer-events-none when hidden
        className
      )}
      onClick={handleScrollToBottom}
      aria-label="Scroll to bottom"
      {...props}
    >
      <IconArrowDown className="h-5 w-5" />
      <span className="sr-only">Scroll to bottom</span>
    </Button>
  )
}