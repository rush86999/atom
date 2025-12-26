import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    children: React.ReactNode;
}

interface DialogContentProps {
    children: React.ReactNode;
    className?: string;
}

interface DialogHeaderProps {
    children: React.ReactNode;
    className?: string;
}

interface DialogTitleProps {
    children: React.ReactNode;
    className?: string;
}

interface DialogFooterProps {
    children: React.ReactNode;
    className?: string;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onOpenChange(false);
        };

        if (open) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        }

        return () => {
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = 'unset';
        };
    }, [open, onOpenChange]);

    if (!open) return null;

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
                className="fixed inset-0 bg-black/50"
                onClick={() => onOpenChange(false)}
                aria-hidden="true"
            />
            {children}
        </div>,
        document.body
    );
}

export function DialogContent({ children, className }: DialogContentProps) {
    return (
        <div
            className={cn(
                "relative w-full transform rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800",
                className
            )}
            role="dialog"
            aria-modal="true"
        >
            {children}
        </div>
    );
}

export function DialogHeader({ children, className }: DialogHeaderProps) {
    return (
        <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}>
            {children}
        </div>
    );
}

export function DialogTitle({ children, className }: DialogTitleProps) {
    return (
        <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>
            {children}
        </h2>
    );
}

export function DialogDescription({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <p className={cn("text-sm text-gray-500 dark:text-gray-400", className)}>
            {children}
        </p>
    );
}

export function DialogFooter({ children, className }: DialogFooterProps) {
    return (
        <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}>
            {children}
        </div>
    );
}

// DialogTrigger - for controlled dialogs, this is a passthrough wrapper
export function DialogTrigger({
    children,
    asChild = false,
    ...props
}: {
    children: React.ReactNode;
    asChild?: boolean;
    onClick?: () => void;
}) {
    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement<any>, props);
    }
    return <span {...props}>{children}</span>;
}
