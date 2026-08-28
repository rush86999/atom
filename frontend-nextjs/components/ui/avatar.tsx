import React from 'react';
import { cn } from '@/lib/utils';

interface AvatarProps {
    className?: string;
    style?: React.CSSProperties;
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
    style?: React.CSSProperties;
}

export function Avatar({ className, style, children }: AvatarProps) {
    return (
        <div className={cn("relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full", className)} style={style}>
            {children}
        </div>
    );
}

export function AvatarImage({ src, alt, className }: AvatarImageProps) {
    if (!src) return null;

    return (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
            src={src}
            alt={alt || "Avatar"}
            className={cn("aspect-square h-full w-full", className)}
        />
    );
}

export function AvatarFallback({ children, className, style }: AvatarFallbackProps) {
    return (
        <div className={cn("flex h-full w-full items-center justify-center rounded-full bg-muted", className)} style={style}>
            {children}
        </div>
    );
}
