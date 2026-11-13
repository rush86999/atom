'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle, Package, RefreshCw, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card'
import {
    describeSkillPackageListFailure,
    listSkillPackages,
    type SkillPackageSummary,
} from '@/lib/skill-packages'
import { getCurrentUserId } from '@/lib/identity'
import {
    SkillPackageDeleteError,
    deleteSkillPackage,
    newSkillPackageDeleteOperationId,
    skillPackageDeleteFailureMessage,
    skillPackageDeleteSuccessMessage,
} from '@/lib/skill-package-delete'

export interface SkillPackageListProps {
    /**
     * Bump after a successful create so the published catalogue re-reads.
     * Mount (0) already loads the list.
     */
    refreshSignal?: number
}

type PackageNotice = {
    tone: 'success' | 'error'
    message: string
    operationId?: string
}

/**
 * Where uncertain/in-flight operation ids survive a page reload. The backend
 * keys its durable receipt on the operation id, so losing it across a reload
 * would turn a recoverable interrupted deletion into a fresh, unrelated
 * operation (and potentially a false 404).
 */
const OPERATION_STORAGE_KEY = 'atom:skill-package-delete:operations'

type StoredOperations = {
    owner: string
    ids: Record<string, string>
}

function readStoredOperationIds(owner: string): Record<string, string> {
    if (typeof window === 'undefined') return {}
    try {
        const raw = window.sessionStorage.getItem(OPERATION_STORAGE_KEY)
        if (!raw) return {}
        const parsed = JSON.parse(raw) as Partial<StoredOperations> | null
        if (
            !parsed ||
            parsed.owner !== owner ||
            !parsed.ids ||
            typeof parsed.ids !== 'object' ||
            Array.isArray(parsed.ids)
        ) {
            return {}
        }
        return Object.entries(parsed.ids).reduce((kept, [name, id]) => {
            if (typeof id === 'string' && id.length > 0) kept[name] = id
            return kept
        }, {} as Record<string, string>)
    } catch {
        return {}
    }
}

function persistOperationIds(
    owner: string,
    ids: Record<string, string>,
): void {
    if (typeof window === 'undefined') return
    try {
        if (Object.keys(ids).length === 0) {
            window.sessionStorage.removeItem(OPERATION_STORAGE_KEY)
            return
        }
        const stored: StoredOperations = { owner, ids }
        window.sessionStorage.setItem(
            OPERATION_STORAGE_KEY,
            JSON.stringify(stored),
        )
    } catch {
        // Storage is an optimization for reload recovery; the in-memory id
        // remains stable even when the browser refuses the write.
    }
}

const showsOperationId = (outcome: SkillPackageDeleteError['outcome']): boolean =>
    outcome === 'partial' ||
    outcome === 'unknown' ||
    outcome === 'not_applied' ||
    outcome === 'conflict'

/**
 * Published Skill Builder packages with verified deletion.
 *
 * Mirrors the verified document-delete conventions: the row is only removed
 * on a confirmed receipt; partial/unknown outcomes keep the row, disable a
 * blind repeat and retain the operation id so a refresh + explicit retry
 * replays the SAME operation.
 */
export function SkillPackageList({ refreshSignal = 0 }: SkillPackageListProps) {
    const [packages, setPackages] = useState<SkillPackageSummary[]>([])
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [deleting, setDeleting] = useState<string | null>(null)
    const [notice, setNotice] = useState<PackageNotice | null>(null)
    // Operation ids for attempts that are in flight or still unreconciled.
    // A `do_not_repeat` outcome keeps its id here (and in sessionStorage)
    // across refreshes/reloads so the next explicit attempt resumes that
    // operation instead of starting a new one.
    const owner = useRef(getCurrentUserId()).current
    const operationIds = useRef<Record<string, string>>(
        readStoredOperationIds(owner),
    )
    const [unreconciled, setUnreconciled] = useState<string[]>([])
    const requestSeq = useRef(0)

    const rememberOperationId = useCallback(
        (name: string, operationId: string | null) => {
            const next = { ...operationIds.current }
            if (operationId) next[name] = operationId
            else delete next[name]
            operationIds.current = next
            persistOperationIds(owner, next)
        },
        [owner],
    )

    const loadPackages = useCallback(async () => {
        const seq = ++requestSeq.current
        setLoading(true)
        setLoadError(null)
        try {
            const next = await listSkillPackages()
            if (seq !== requestSeq.current) return
            setPackages(next)
            // Reconciliation step: if a package disappeared after an
            // uncertain outcome its id is finished; if it is still present the
            // id is retained and the delete control re-enables.
            const present = new Set(next.map((pkg) => pkg.name))
            const kept = Object.keys(operationIds.current).reduce(
                (acc, name) => {
                    if (present.has(name)) acc[name] = operationIds.current[name]
                    return acc
                },
                {} as Record<string, string>,
            )
            operationIds.current = kept
            persistOperationIds(owner, kept)
            setUnreconciled([])
        } catch (error) {
            if (seq !== requestSeq.current) return
            setPackages([])
            setLoadError(describeSkillPackageListFailure(error))
        } finally {
            if (seq === requestSeq.current) setLoading(false)
        }
    }, [owner])

    useEffect(() => {
        void loadPackages()
    }, [loadPackages, refreshSignal])

    const handleDelete = useCallback(async (pkg: SkillPackageSummary) => {
        if (deleting) return
        if (!window.confirm(`Delete skill package "${pkg.name}"? This removes the published package directory and cannot be undone.`)) {
            return
        }

        // Stable id: reused for a retry of this same intention.
        const operationId = operationIds.current[pkg.name] ?? newSkillPackageDeleteOperationId()
        rememberOperationId(pkg.name, operationId)
        setDeleting(pkg.name)
        setNotice(null)

        try {
            const receipt = await deleteSkillPackage(pkg.name, operationId)
            rememberOperationId(pkg.name, null)
            setPackages((current) => current.filter((row) => row.name !== pkg.name))
            setUnreconciled((current) => current.filter((name) => name !== pkg.name))
            setNotice({
                tone: 'success',
                message: skillPackageDeleteSuccessMessage(receipt.outcome),
                operationId: receipt.operationId,
            })
        } catch (error) {
            const failure = error instanceof SkillPackageDeleteError
                ? error
                : new SkillPackageDeleteError({ outcome: 'unknown' })
            const canonicalId = failure.operationId ?? operationId

            if (failure.outcome === 'not_found') {
                // Definitively absent: the row is stale. This is not a claim
                // that this request deleted it.
                rememberOperationId(pkg.name, null)
                setPackages((current) => current.filter((row) => row.name !== pkg.name))
                setUnreconciled((current) => current.filter((name) => name !== pkg.name))
            } else if (failure.replay === 'same_operation') {
                // Nothing was applied; the same operation id is safe to retry.
                rememberOperationId(pkg.name, canonicalId)
            } else if (failure.replay === 'do_not_repeat') {
                // Uncertain effect: keep the row, disable a blind repeat and
                // retain the id for the post-refresh reconciliation replay.
                rememberOperationId(pkg.name, canonicalId)
                setUnreconciled((current) =>
                    current.includes(pkg.name) ? current : [...current, pkg.name],
                )
            } else {
                // Refused before any effect; a later attempt is a new
                // intention (a reused id could be bound to other work).
                rememberOperationId(pkg.name, null)
            }

            setNotice({
                tone: 'error',
                message: skillPackageDeleteFailureMessage(failure.outcome),
                operationId: showsOperationId(failure.outcome) ? canonicalId : undefined,
            })
        } finally {
            setDeleting(null)
        }
    }, [deleting, rememberOperationId])

    return (
        <Card className="bg-zinc-900 border-zinc-800" data-testid="skill-package-list">
            <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                <div>
                    <CardTitle className="text-gray-900 dark:text-white flex items-center gap-2">
                        <Package className="w-4 h-4 text-primary" />
                        Published packages
                    </CardTitle>
                    <CardDescription className="text-zinc-400">
                        Packages in this workspace that agents can load.
                    </CardDescription>
                </div>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void loadPackages()}
                    disabled={loading}
                    data-testid="refresh-skill-packages"
                >
                    <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </CardHeader>
            <CardContent className="space-y-4">
                {notice && (
                    <div
                        data-testid="skill-package-delete-notice"
                        role={notice.tone === 'error' ? 'alert' : 'status'}
                        className={`flex items-start gap-3 rounded-md p-3 text-sm ${notice.tone === 'error'
                            ? 'bg-destructive/10 text-destructive'
                            : 'bg-emerald-500/10 text-emerald-500'
                            }`}
                    >
                        {notice.tone === 'error' ? (
                            <AlertCircle className="h-5 w-5 shrink-0" />
                        ) : (
                            <CheckCircle className="h-5 w-5 shrink-0" />
                        )}
                        <div className="min-w-0">
                            <p className="font-medium">{notice.message}</p>
                            {notice.operationId && (
                                <p
                                    className="mt-1 break-all font-mono text-xs text-zinc-400"
                                    data-testid="skill-package-delete-operation-id"
                                >
                                    Operation: {notice.operationId}
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {loadError ? (
                    <div
                        data-testid="skill-packages-error"
                        role="alert"
                        className="flex items-start gap-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
                    >
                        <AlertCircle className="h-5 w-5 shrink-0" />
                        <div className="min-w-0 flex-1">
                            <p className="font-medium">{loadError}</p>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="mt-3"
                                onClick={() => void loadPackages()}
                                disabled={loading}
                            >
                                Retry
                            </Button>
                        </div>
                    </div>
                ) : loading && packages.length === 0 ? (
                    <p data-testid="skill-packages-loading" className="text-sm text-zinc-400">
                        Loading packages…
                    </p>
                ) : packages.length === 0 ? (
                    <p data-testid="skill-packages-empty" className="text-sm text-zinc-400">
                        No packages published yet.
                    </p>
                ) : (
                    <ul className="divide-y divide-zinc-800" data-testid="skill-packages">
                        {packages.map((pkg) => {
                            const isUnreconciled = unreconciled.includes(pkg.name)
                            return (
                                <li
                                    key={pkg.name}
                                    data-testid={`skill-package-row-${pkg.name}`}
                                    className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                                >
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="truncate font-medium text-gray-900 dark:text-white">
                                                {pkg.name}
                                            </span>
                                            <Badge variant={pkg.hasManifest ? 'secondary' : 'outline'} className="text-xs">
                                                {pkg.hasManifest ? 'manifest' : 'no manifest'}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-zinc-400">
                                            {pkg.files.length} {pkg.files.length === 1 ? 'file' : 'files'}
                                            {' · modified '}
                                            {new Date(pkg.modifiedAt * 1000).toLocaleDateString()}
                                        </p>
                                        {isUnreconciled && (
                                            <p className="mt-1 text-xs text-amber-500">
                                                Deletion not verified — refresh the list before trying again.
                                            </p>
                                        )}
                                    </div>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 shrink-0 self-start text-zinc-400 hover:text-destructive sm:self-center"
                                        aria-label={`Delete ${pkg.name}`}
                                        title={isUnreconciled
                                            ? 'Deletion not verified — refresh the list before trying again'
                                            : 'Delete skill package'}
                                        data-testid={`delete-skill-package-${pkg.name}`}
                                        disabled={deleting !== null || isUnreconciled}
                                        onClick={() => void handleDelete(pkg)}
                                    >
                                        {deleting === pkg.name ? (
                                            <RefreshCw className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Trash2 className="h-4 w-4" />
                                        )}
                                    </Button>
                                </li>
                            )
                        })}
                    </ul>
                )}
            </CardContent>
        </Card>
    )
}

export default SkillPackageList
