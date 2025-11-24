import { cn } from "./button"

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
    size?: "sm" | "md" | "lg" | "xl"
}

export function Spinner({ className, size = "md", ...props }: SpinnerProps) {
    const sizeClasses = {
        sm: "h-4 w-4 border-2",
        md: "h-6 w-6 border-2",
        lg: "h-8 w-8 border-3",
        xl: "h-12 w-12 border-4",
    }

    return (
        <div
            className={cn(
                "animate-spin rounded-full border-current border-t-transparent text-primary",
                sizeClasses[size],
                className
            )}
            {...props}
        >
            <span className="sr-only">Loading...</span>
        </div>
    )
}
