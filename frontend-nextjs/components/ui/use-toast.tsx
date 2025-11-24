import * as React from "react"

type ToastProps = {
    title?: string
    description?: string
    status?: "success" | "error" | "info" | "warning"
    duration?: number
    isClosable?: boolean
}

type ToastActionElement = React.ReactElement

export function useToast() {
    const toast = React.useCallback(({ title, description, status }: ToastProps) => {
        // For now, simple alert or console log as placeholder until a full Toast provider is added
        console.log(`[TOAST - ${status?.toUpperCase()}]: ${title} - ${description}`)
        // In a real app, we'd dispatch to a context
    }, [])

    return toast
}
