'use client'

import { useEffect, useRef } from 'react'

interface VoiceVisualizerProps {
    mode: 'idle' | 'listening' | 'processing' | 'speaking'
}

export function VoiceVisualizer({ mode }: VoiceVisualizerProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const requestIdRef = useRef<number>()

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        let frame = 0
        const bars = 40
        const width = canvas.width
        const height = canvas.height
        const barWidth = width / bars

        const animate = () => {
            frame++
            ctx.clearRect(0, 0, width, height)

            // Choose color/intensity based on mode
            let baseColor = '100, 116, 139' // slate-500 (idle)
            let amplitude = 10
            let speed = 0.05

            if (mode === 'listening') {
                baseColor = '16, 185, 129' // emerald-500
                amplitude = 40
                speed = 0.2
            } else if (mode === 'processing') {
                baseColor = '249, 115, 22' // orange-500
                amplitude = 20
                speed = 0.1
            } else if (mode === 'speaking') {
                baseColor = '59, 130, 246' // blue-500
                amplitude = 60
                speed = 0.15
            }

            for (let i = 0; i < bars; i++) {
                // Generate wave effect
                const t = frame * speed + i * 0.5
                const noise = Math.sin(t) * Math.cos(t * 0.5)
                const barHeight = 10 + Math.abs(noise) * amplitude

                const x = i * barWidth
                const y = (height - barHeight) / 2

                ctx.fillStyle = `rgb(${baseColor})`
                // Add glow in active modes
                if (mode !== 'idle') {
                    ctx.shadowBlur = 15
                    ctx.shadowColor = `rgb(${baseColor})`
                } else {
                    ctx.shadowBlur = 0
                }

                // Rounded pill shape
                ctx.beginPath();
                ctx.roundRect(x + 2, y, barWidth - 4, barHeight, 4);
                ctx.fill();
            }

            requestIdRef.current = requestAnimationFrame(animate)
        }

        animate()

        return () => {
            if (requestIdRef.current) cancelAnimationFrame(requestIdRef.current)
        }
    }, [mode])

    return (
        <canvas
            ref={canvasRef}
            width={400}
            height={100}
            className="w-full h-24 pointer-events-none"
        />
    )
}
