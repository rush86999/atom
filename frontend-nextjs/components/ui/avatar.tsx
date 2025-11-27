import React from 'react';
import { cn } from '@/lib/utils';

interface AvatarProps {
    className?: string;
    children?: React.ReactNode;
}

interface AvatarImageProps {
    src?: string;
    alt?: string;
    className?: string;
}

interface AvatarFallbackProps {
    children: React.ReactNode;
    className?: string;
}

export function Avatar({ className, children }: AvatarProps) {
    return (
        <div className={cn("relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full", className)}>
            {children}
        </div>
    );
}

export function AvatarImage({ src, alt, className }: AvatarImageProps) {
    if (!src) return null;

    return (
        <img
            src={src}
            alt={alt || "Avatar"}
            className={cn("aspect-square h-full w-full", className)}
        />
    );
}

export function AvatarFallback({ children, className }: AvatarFallbackProps) {
    return (
        <div className={cn("flex h-full w-full items-center justify-center rounded-full bg-muted", className)}>
            {children}
        </div>
    );
}
