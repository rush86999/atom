import * as React from "react"
import { cn } from "../../utils/cn"

const Progress = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { value?: number, indicatorClassName?: string }
>(({ className, value, indicatorClassName, ...props }, ref) => (
    <div
        ref={ref}
        className={cn(
            "relative h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800",
            className
        )}
        {...props}
    >
        <div
            className={cn("h-full w-full flex-1 bg-blue-600 transition-all", indicatorClassName)}
            style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
    </div>
))
Progress.displayName = "Progress"

export { Progress }
