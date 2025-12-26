import * as React from "react"
import { cn } from "../../utils/cn"

interface TooltipProviderProps {
    children: React.ReactNode
    delayDuration?: number
    skipDelayDuration?: number
}

interface TooltipProps {
    children: React.ReactNode
}

interface TooltipTriggerProps {
    children: React.ReactNode
    asChild?: boolean
}

interface TooltipContentProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode
    sideOffset?: number
}

const TooltipContext = React.createContext<{ open: boolean; setOpen: (open: boolean) => void } | null>(null)

const TooltipProvider: React.FC<TooltipProviderProps> = ({ children }) => {
    return <>{children}</>
}

const Tooltip: React.FC<TooltipProps> = ({ children }) => {
    const [open, setOpen] = React.useState(false)
    return (
        <TooltipContext.Provider value={{ open, setOpen }}>
            <div className="relative inline-block">
                {children}
            </div>
        </TooltipContext.Provider>
    )
}

const TooltipTrigger: React.FC<TooltipTriggerProps> = ({ children, asChild }) => {
    const context = React.useContext(TooltipContext)

    const handleMouseEnter = () => context?.setOpen(true)
    const handleMouseLeave = () => context?.setOpen(false)

    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement<any>, {
            onMouseEnter: handleMouseEnter,
            onMouseLeave: handleMouseLeave,
        })
    }

    return (
        <span onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
            {children}
        </span>
    )
}

const TooltipContent = React.forwardRef<HTMLDivElement, TooltipContentProps>(
    ({ className, children, sideOffset = 4, ...props }, ref) => {
        const context = React.useContext(TooltipContext)

        if (!context?.open) return null

        return (
            <div
                ref={ref}
                role="tooltip"
                className={cn(
                    "absolute z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95",
                    "bottom-full left-1/2 -translate-x-1/2 mb-2",
                    className
                )}
                style={{ marginBottom: sideOffset }}
                {...props}
            >
                {children}
            </div>
        )
    }
)
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
