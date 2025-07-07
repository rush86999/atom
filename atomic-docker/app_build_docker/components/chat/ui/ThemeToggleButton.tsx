'use client' // Add use client for Next.js App Router if needed, or remove if not applicable

import React from 'react';
import { useTheme } from '@lib/contexts/ThemeContext';
import { Button } from './button'; // Assuming button is in the same directory or path is correct
import { IconSun, IconMoon } from './icons'; // Assuming icons are in the same directory
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@components/chat/ui/tooltip";

export const ThemeToggleButton: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <TooltipProvider delayDuration={300}>
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="h-9 w-9 rounded-full text-gray-600 hover:text-sky-600 dark:text-gray-400 dark:hover:text-sky-500"
                aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
                >
                {theme === 'light' ? (
                    <IconMoon className="h-5 w-5" />
                ) : (
                    <IconSun className="h-5 w-5" />
                )}
                </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
                 {theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            </TooltipContent>
        </Tooltip>
    </TooltipProvider>
  );
};
