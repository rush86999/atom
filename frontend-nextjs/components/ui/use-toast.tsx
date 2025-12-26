import * as React from "react"
import { X } from "lucide-react"
import { cn } from "./button"

type ToastProps = {
    id: string
    title?: string
    description?: string
    variant?: "default" | "success" | "error" | "warning"
    duration?: number
}

type ToastContextType = {
    toasts: ToastProps[]
    toast: (props: Omit<ToastProps, "id">) => void
    dismiss: (id: string) => void
}

const ToastContext = React.createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = React.useState<ToastProps[]>([])

    const toast = React.useCallback((props: Omit<ToastProps, "id">) => {
        const id = Math.random().toString(36).substring(7)
        const duration = props.duration ?? 5000

        setToasts((prev) => [...prev, { ...props, id }])

        if (duration > 0) {
            setTimeout(() => {
                dismiss(id)
            }, duration)
        }
    }, [])

    const dismiss = React.useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
    }, [])

    return (
        <ToastContext.Provider value={{ toasts, toast, dismiss }}>
            {children}
            <ToastContainer toasts={toasts} dismiss={dismiss} />
        </ToastContext.Provider>
    )
}

function ToastContainer({ toasts, dismiss }: { toasts: ToastProps[]; dismiss: (id: string) => void }) {
    if (toasts.length === 0) return null

    return (
        <div className="fixed top-0 right-0 z-50 p-4 space-y-2 max-w-md w-full pointer-events-none">
            {toasts.map((toast) => (
                <Toast key={toast.id} {...toast} onDismiss={() => dismiss(toast.id)} />
            ))}
        </div>
    )
}

function Toast({ title, description, variant = "default", onDismiss }: ToastProps & { onDismiss: () => void }) {
    const variantStyles = {
        default: "bg-white border-gray-200 text-gray-900",
        success: "bg-green-50 border-green-200 text-green-900",
        error: "bg-red-50 border-red-200 text-red-900",
        warning: "bg-yellow-50 border-yellow-200 text-yellow-900",
    }

    return (
        <div
            className={cn(
                "pointer-events-auto flex items-start gap-3 rounded-lg border p-4 shadow-lg transition-all animate-in slide-in-from-right",
                variantStyles[variant]
            )}
        >
            <div className="flex-1">
                {title && <div className="font-semibold">{title}</div>}
                {description && <div className="text-sm opacity-90 mt-1">{description}</div>}
            </div>
            <button
                onClick={onDismiss}
                className="opacity-70 hover:opacity-100 transition-opacity"
                aria-label="Close toast"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    )
}

export function useToast() {
    const context = React.useContext(ToastContext)
    if (!context) {
        throw new Error("useToast must be used within ToastProvider")
    }
    return { toast: context.toast, dismiss: context.dismiss, toasts: context.toasts }
}
