import * as React from "react"
import { Check } from "lucide-react"
import { cn } from "../../utils/cn"

const Checkbox = React.forwardRef<
    HTMLInputElement,
    React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => {
    return (
        <div className="relative inline-flex items-center">
            <input
                type="checkbox"
                className={cn(
                    "peer h-4 w-4 shrink-0 appearance-none rounded-sm border border-gray-300 ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 checked:bg-blue-600 checked:border-blue-600",
                    className
                )}
                ref={ref}
                {...props}
            />
            <Check className="absolute left-0 top-0 h-4 w-4 hidden peer-checked:block pointer-events-none text-white" />
        </div>
    )
})
Checkbox.displayName = "Checkbox"

export { Checkbox }
