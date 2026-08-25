import React, { useEffect, useState } from 'react';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Loader2, GraduationCap, Eye, BookOpen, ArrowRight } from 'lucide-react';
import { AgentMaturityGuide, getAgentMaturityGuide } from '@/lib/agent-onboarding-api';

interface AgentMaturityGuideDialogProps {
  agentId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const LEVEL_COLORS: Record<string, string> = {
  student: 'bg-slate-100 text-slate-700 border-slate-300',
  intern: 'bg-blue-50 text-blue-700 border-blue-300',
  supervised: 'bg-purple-50 text-purple-700 border-purple-300',
  autonomous: 'bg-orange-50 text-orange-700 border-orange-300',
};

/**
 * "When will this agent be useful?" — a per-agent readiness report in plain
 * language: what it can do today, how its learning is progressing, and
 * exactly what advances it to the next maturity level.
 */
export function AgentMaturityGuideDialog({ agentId, open, onOpenChange }: AgentMaturityGuideDialogProps) {
  const [guide, setGuide] = useState<AgentMaturityGuide | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !agentId) return;
    setIsLoading(true);
    setError(null);
    getAgentMaturityGuide(agentId)
      .then(setGuide)
      .catch(() => setError('Could not load the maturity guide for this agent.'))
      .finally(() => setIsLoading(false));
  }, [open, agentId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl" data-testid="agent-maturity-guide">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-blue-500" />
            {guide ? `${guide.agent_name} — maturity & readiness` : 'Maturity & readiness'}
          </DialogTitle>
          <DialogDescription>
            What this agent can do today, and what it needs to do more.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center justify-center py-8 text-gray-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading readiness report...
          </div>
        )}
        {error && <p className="text-sm text-red-600 py-4">{error}</p>}

        {guide && (
          <div className="space-y-4 py-1" data-testid="agent-maturity-guide-content">
            {/* Current level */}
            <div className="flex items-center gap-2">
              <Badge className={LEVEL_COLORS[guide.current_level] || LEVEL_COLORS.student}>
                {guide.current_level}
              </Badge>
              {guide.next_level && (
                <span className="flex items-center text-xs text-gray-500">
                  <ArrowRight className="h-3 w-3 mx-1" /> next: {guide.next_level}
                </span>
              )}
              <Badge variant="outline">{guide.learning_progress.role}</Badge>
            </div>

            {/* Plain-language level guide */}
            <div className="text-sm bg-gray-50 dark:bg-gray-800/60 rounded-lg p-3 border border-gray-100 dark:border-gray-700">
              <p><span className="font-medium text-green-700 dark:text-green-400">Does now:</span> {guide.level_guide.what_it_can_do}</p>
              <p className="mt-1"><span className="font-medium text-red-600 dark:text-red-400">Doesn&apos;t yet:</span> {guide.level_guide.what_it_cannot_do}</p>
              <p className="mt-1"><span className="font-medium text-blue-700 dark:text-blue-400">Useful for:</span> {guide.level_guide.useful_for}</p>
            </div>

            {/* Readiness progress */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500 font-medium">Learning progress</span>
                <span className="text-gray-400">
                  {Math.round(guide.readiness.confidence * 100)}% /{' '}
                  {Math.round(guide.readiness.confidence_needed_for_training_review * 100)}% to graduation review
                </span>
              </div>
              <Progress
                value={(guide.readiness.confidence / guide.readiness.confidence_needed_for_training_review) * 100}
                data-testid="maturity-readiness-progress"
              />
              <p className="mt-1.5 text-xs text-gray-500" data-testid="maturity-readiness-note">{guide.readiness.note}</p>
            </div>

            {/* Learning pathway counts */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex items-center gap-2 border rounded p-2" data-testid="maturity-lessons">
                <BookOpen className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="font-semibold">{guide.learning_progress.lessons_from_teacher}</p>
                  <p className="text-xs text-gray-500">lessons from Atom</p>
                </div>
              </div>
              <div className="flex items-center gap-2 border rounded p-2" data-testid="maturity-observations">
                <Eye className="h-4 w-4 text-purple-500" />
                <div>
                  <p className="font-semibold">{guide.learning_progress.observations}</p>
                  <p className="text-xs text-gray-500">things observed</p>
                </div>
              </div>
            </div>

            {/* Mastery topics */}
            {(guide.mastery.mastered.length > 0 || Object.keys(guide.mastery.in_progress).length > 0) && (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1.5">Skill topics</p>
                <div className="flex flex-wrap gap-1.5">
                  {guide.mastery.mastered.map((t) => (
                    <Badge key={t} className="bg-green-50 text-green-700 border-green-300" variant="outline">✓ {t}</Badge>
                  ))}
                  {Object.entries(guide.mastery.in_progress).map(([t, n]) => (
                    <Badge key={t} variant="outline" className="text-gray-500">
                      {t} {n}/{guide.mastery.threshold}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* How to advance */}
            <div className="text-sm border-l-4 border-blue-300 pl-3 py-1 text-gray-600 dark:text-gray-300" data-testid="maturity-advance">
              <p className="font-medium text-gray-800 dark:text-gray-100">
                To reach {guide.next_level || 'the top'}:
              </p>
              <p>{guide.how_to_advance}</p>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
