import * as React from "react"
import { cn } from "../../utils/cn"

interface SliderProps extends React.HTMLAttributes<HTMLDivElement> {
    value: number
    onValueChange: (value: number) => void
    min?: number
    max?: number
    step?: number
}

const Slider = React.forwardRef<HTMLDivElement, SliderProps>(
    ({ className, value, onValueChange, min = 0, max = 100, step = 1, ...props }, ref) => {
        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            onValueChange(Number(e.target.value))
        }

        return (
            <div ref={ref} className={cn("relative w-full", className)} {...props}>
                <input
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={value}
                    onChange={handleChange}
                    className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider-thumb"
                />
                <style jsx>{`
          input[type="range"]::-webkit-slider-thumb {
            appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
          }
          input[type="range"]::-moz-range-thumb {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
            border: none;
          }
        `}</style>
            </div>
        )
    }
)
Slider.displayName = "Slider"

export { Slider }
