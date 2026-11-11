import React, { useState, useSyncExternalStore } from 'react'
import Link from 'next/link'
import { Lightbulb, ChevronDown, GraduationCap, ShieldQuestion, Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useProductProfile } from '@/lib/product-profile'

const STORAGE_KEY = 'atom.agent_guide.dismissed.v1'

const subscribeToDismissal = (callback: () => void) => {
    window.addEventListener('storage', callback)
    return () => window.removeEventListener('storage', callback)
}

const getDismissedSnapshot = () => {
    try {
        return window.localStorage.getItem(STORAGE_KEY) === '1'
    } catch {
        return false
    }
}

const getServerDismissedSnapshot = () => true

/**
 * "Managing AI employees" onboarding guide for the Agent Control Center.
 *
 * Surfaces the three things a first-time manager needs to know — the
 * train-to-autonomy lifecycle, their per-tier supervision duty, and how an
 * employee's role/job-description scopes its memory — without burying them
 * in docs. Dismissal is remembered (localStorage) and reversible.
 */
export function EmployeeOnboardingGuide() {
    const storedDismissed = useSyncExternalStore(
        subscribeToDismissal,
        getDismissedSnapshot,
        getServerDismissedSnapshot
    )
    const [dismissedOverride, setDismissedOverride] = useState<boolean | null>(null)
    const [expanded, setExpanded] = useState(true)
    const dismissed = dismissedOverride ?? storedDismissed
    const { isCapabilityEnabled } = useProductProfile()
    const marketplaceEnabled = isCapabilityEnabled('marketplace')

    const dismiss = () => {
        setDismissedOverride(true)
        try {
            localStorage.setItem(STORAGE_KEY, '1')
        } catch { /* ignore */ }
    }

    if (dismissed) {
        return (
            <button
                onClick={() => {
                    setDismissedOverride(false)
                    setExpanded(true)
                }}
                data-testid="agent-guide-restore"
                className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
            >
                <Lightbulb className="w-4 h-4" /> How to manage AI employees
            </button>
        )
    }

    return (
        <div
            data-testid="agent-guide"
            className="bg-white dark:bg-gray-800 border border-blue-100 dark:border-blue-900 rounded-lg shadow-sm"
        >
            <div className="flex items-center justify-between px-4 py-3">
                <button
                    onClick={() => setExpanded(e => !e)}
                    className="flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-100"
                    data-testid="agent-guide-toggle"
                >
                    <Lightbulb className="w-4 h-4 text-blue-500" />
                    How to manage AI employees
                    <ChevronDown
                        className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
                    />
                </button>
                <Button variant="ghost" size="sm" onClick={dismiss} data-testid="agent-guide-dismiss">
                    Got it
                </Button>
            </div>

            {expanded && (
                <div className="px-4 pb-4 grid gap-4 md:grid-cols-3 text-sm text-gray-600 dark:text-gray-300">
                    <section data-testid="agent-guide-lifecycle">
                        <h3 className="flex items-center gap-1.5 font-semibold text-gray-800 dark:text-gray-100 mb-1">
                            <GraduationCap className="w-4 h-4 text-slate-500" /> 1. Hire &amp; train
                        </h3>
                        <p>
                            {marketplaceEnabled ? (
                                <>
                                    Spawn an employee from a{' '}
                                    <Link href="/marketplace" className="text-blue-600 underline">template</Link>,
                                    then run it on real tasks.
                                </>
                            ) : (
                                <>Create an employee, then run it on real tasks.</>
                            )}{' '}
                            Clean runs build experience toward the next stage, but
                            they do not promote an employee by themselves. Normal
                            promotion also needs the readiness requirements for that
                            stage and a review of the employee&apos;s actual work for
                            the role. An allowed owner exception is recorded with its
                            reason; domain selectors do not create exemptions. Domain
                            rules can still require human review.
                        </p>
                    </section>

                    <section data-testid="agent-guide-supervision">
                        <h3 className="flex items-center gap-1.5 font-semibold text-gray-800 dark:text-gray-100 mb-1">
                            <ShieldQuestion className="w-4 h-4 text-purple-500" /> 2. Supervise by tier
                        </h3>
                        <p>
                            <strong>Student</strong> employees are read-only: they
                            search, read and summarize but cannot change anything.
                            <strong> Interns</strong> draft and propose work for you to
                            start. <strong>Supervised</strong> employees handle routine
                            work under the current action policy; high-risk steps and
                            domain rules still pause for review. Review requests in{' '}
                            <Link href="/approvals" className="text-blue-600 underline">Approvals</Link> and
                            correct mistakes via 👍/👎 on reasoning steps — feedback
                            directly shapes what they learn.
                        </p>
                    </section>

                    <section data-testid="agent-guide-memory">
                        <h3 className="flex items-center gap-1.5 font-semibold text-gray-800 dark:text-gray-100 mb-1">
                            <Database className="w-4 h-4 text-blue-500" /> 3. Scope their memory
                        </h3>
                        <p>
                            An employee&apos;s <em>category</em> (its role) and
                            <em> description</em> (its job description) decide which
                            company data you make available — invoices, leads, tickets
                            — it recalls at work. Keep both specific: a
                            &ldquo;Finance&rdquo; employee sees the books, not the
                            support inbox.
                        </p>
                    </section>
                </div>
            )}
        </div>
    )
}

export default EmployeeOnboardingGuide
