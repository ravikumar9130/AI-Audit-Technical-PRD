'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Loader2,
  ArrowLeft,
  MessageSquare,
  Lightbulb,
  AlertTriangle,
  CheckCircle2,
  FileText,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface TranscriptSegment {
  transcript_id: number;
  speaker_label: string;
  start_time: number;
  end_time: number;
  text: string;
  confidence?: number;
  emotion?: string;
}

interface TranscriptData {
  call_id: number;
  segments: TranscriptSegment[];
  full_text: string;
}

interface EvaluationData {
  result_id: number;
  call_id: number;
  overall_score: number;
  ses_score?: number;
  sqs_score?: number;
  res_score?: number;
  pillar_scores?: Record<string, number>;
  compliance_flags?: Record<string, unknown>;
  fatal_flaw_detected: boolean;
  fatal_flaw_type?: string;
  summary?: string;
  recommendations?: string[];
  sentiment_score?: number;
  created_at: string;
}

const DASHBOARD_BACK: Record<string, { href: string; label: string }> = {
  Agent: { href: '/dashboard/agent', label: 'Cockpit' },
  Manager: { href: '/dashboard/manager', label: 'War Room' },
  CXO: { href: '/dashboard/cxo', label: 'Executive' },
  Admin: { href: '/dashboard/agent', label: 'Dashboard' },
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function isAgentSpeaker(label: string): boolean {
  const lower = (label || '').toLowerCase();
  return lower.includes('agent') || lower === 'speaker 1';
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-lg bg-muted/60', className)}
      aria-hidden
    />
  );
}

export default function CallDetailPage() {
  const params = useParams();
  const callId = Number(params.callId);
  const { token, user } = useAuth();
  const [call, setCall] = useState<{ call_id: number; status: string; created_at: string } | null>(null);
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [results, setResults] = useState<EvaluationData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchCallData = useCallback((): Promise<string | undefined> => {
    if (!token || Number.isNaN(callId)) return Promise.resolve(undefined);
    return Promise.all([
      api.calls.get(token, callId).catch(() => null),
      api.calls.getTranscript(token, callId).catch(() => null),
      api.calls.getResults(token, callId).catch(() => null),
    ]).then(([c, t, r]) => {
      setCall((prev) => c ?? prev);
      setTranscript((prev) => t ?? prev);
      setResults((prev) => r ?? prev);
      if (!c && !t) setError('Call not found');
      return c?.status;
    });
  }, [token, callId]);

  useEffect(() => {
    if (!token || Number.isNaN(callId)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetchCallData()
      .then(() => {})
      .catch((err) => setError(err?.message ?? 'Failed to load'))
      .finally(() => setLoading(false));
  }, [token, callId, fetchCallData]);

  useEffect(() => {
    const status = call?.status ?? '';
    if (status !== 'processing' && status !== 'queued') return;
    const interval = setInterval(() => {
      fetchCallData().then((newStatus) => {
        if (newStatus === 'completed' || newStatus === 'failed') clearInterval(interval);
      });
    }, 8000);
    return () => clearInterval(interval);
  }, [call?.status, callId, fetchCallData]);

  const back = user ? DASHBOARD_BACK[user.role] ?? DASHBOARD_BACK.Agent : DASHBOARD_BACK.Agent;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-1">
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
        <Skeleton className="h-64" />
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </div>
    );
  }

  if (error || (!call && !transcript)) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" asChild className="gap-2">
          <Link href={back.href}>
            <ArrowLeft className="h-4 w-4" />
            Back to {back.label}
          </Link>
        </Button>
        <Card className="border-destructive/30 bg-destructive/5 p-8 text-center">
          <AlertTriangle className="mx-auto mb-3 h-10 w-10 text-destructive" />
          <p className="font-medium text-foreground">{error ?? 'Call not found'}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            The call may have been deleted or you don’t have access.
          </p>
          <Button asChild className="mt-4">
            <Link href={back.href}>Return to {back.label}</Link>
          </Button>
        </Card>
      </div>
    );
  }

  const status = call?.status ?? 'unknown';
  const isCompleted = status === 'completed';
  const recommendations = results?.recommendations ?? [];
  const hasCoaching =
    isCompleted &&
    (recommendations.length > 0 || !!results?.summary || !!results?.fatal_flaw_detected);
  const hasTranscript = transcript?.segments && transcript.segments.length > 0;

  return (
    <div className="space-y-6 pb-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="outline" size="icon" asChild className="shrink-0 rounded-xl">
            <Link href={back.href} aria-label={`Back to ${back.label}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">Call #{callId}</h1>
            <p className="text-sm text-muted-foreground">
              {call?.created_at
                ? new Date(call.created_at).toLocaleString(undefined, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })
                : '—'}
            </p>
          </div>
          <StatusBadge status={status} />
        </div>
      </header>

      {hasTranscript && (status === 'processing' || status === 'queued') && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-200/50 bg-amber-50/80 px-4 py-3 text-sm text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-200">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
          <span>Transcript ready. Scoring in progress — this page updates automatically.</span>
        </div>
      )}

      {isCompleted && results && (
        <Card className="overflow-hidden border-emerald-200/50 dark:border-emerald-900/30">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              Score & summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-6">
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Overall
                </p>
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      'text-3xl font-bold tabular-nums',
                      results.overall_score >= 80 && 'text-emerald-600 dark:text-emerald-400',
                      results.overall_score >= 60 &&
                        results.overall_score < 80 &&
                        'text-amber-600 dark:text-amber-400',
                      results.overall_score < 60 && 'text-rose-600 dark:text-rose-400'
                    )}
                  >
                    {results.overall_score.toFixed(0)}
                  </span>
                  <span className="text-muted-foreground">/ 100</span>
                </div>
                <Progress
                  value={results.overall_score}
                  className="h-2 w-full max-w-[140px]"
                />
              </div>
              {[results.ses_score, results.sqs_score, results.res_score].some((s) => s != null) && (
                <div className="flex gap-4 border-l border-border pl-4">
                  {results.ses_score != null && (
                    <div>
                      <p className="text-xs text-muted-foreground">SES</p>
                      <p className="text-lg font-semibold tabular-nums">
                        {results.ses_score.toFixed(1)}
                      </p>
                    </div>
                  )}
                  {results.sqs_score != null && (
                    <div>
                      <p className="text-xs text-muted-foreground">SQS</p>
                      <p className="text-lg font-semibold tabular-nums">
                        {results.sqs_score.toFixed(1)}
                      </p>
                    </div>
                  )}
                  {results.res_score != null && (
                    <div>
                      <p className="text-xs text-muted-foreground">RES</p>
                      <p className="text-lg font-semibold tabular-nums">
                        {results.res_score.toFixed(1)}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
            {results.summary && (
              <p className="border-t border-border pt-3 text-sm text-muted-foreground leading-relaxed">
                {results.summary}
              </p>
            )}
            {results.fatal_flaw_detected && (
              <div
                className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
                role="alert"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {results.fatal_flaw_type
                    ? `Fatal flaw: ${results.fatal_flaw_type}`
                    : 'A critical compliance issue was detected on this call.'}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {hasCoaching && (
        <Card className="border-amber-200/50 bg-gradient-to-br from-amber-50/80 to-transparent dark:border-amber-900/30 dark:from-amber-950/20 dark:to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/20">
                <Lightbulb className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </span>
              Coaching hints
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Use these to improve your next calls.
            </p>
          </CardHeader>
          <CardContent className="space-y-2">
            {recommendations.length > 0 ? (
              <ul className="space-y-2" role="list">
                {recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex gap-3 rounded-xl border border-amber-200/50 bg-card/80 px-4 py-3 text-sm shadow-sm transition-shadow hover:shadow dark:border-amber-900/30"
                  >
                    <span
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-xs font-semibold text-amber-700 dark:text-amber-300"
                      aria-hidden
                    >
                      {i + 1}
                    </span>
                    <span className="leading-relaxed">{rec}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-lg border border-border/80 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                No specific recommendations for this call.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <MessageSquare className="h-4 w-4 text-primary" />
            </span>
            Transcript
          </CardTitle>
          {hasTranscript && (
            <p className="text-sm text-muted-foreground">
              {transcript!.segments.length} segment{transcript!.segments.length !== 1 ? 's' : ''}
            </p>
          )}
        </CardHeader>
        <CardContent>
          {hasTranscript ? (
            <div
              className="space-y-3 max-h-[65vh] overflow-y-auto overflow-x-hidden pr-1 scroll-smooth"
              role="region"
              aria-label="Call transcript"
            >
              {transcript!.segments.map((seg) => {
                const agent = isAgentSpeaker(seg.speaker_label);
                return (
                  <div
                    key={seg.transcript_id}
                    className={cn(
                      'rounded-xl border px-4 py-3 text-sm transition-colors',
                      agent
                        ? 'border-primary/25 bg-primary/5'
                        : 'border-border/80 bg-muted/20'
                    )}
                  >
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          'font-semibold capitalize',
                          agent ? 'text-primary' : 'text-muted-foreground'
                        )}
                      >
                        {seg.speaker_label || 'Speaker'}
                      </span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {formatTime(seg.start_time)} – {formatTime(seg.end_time)}
                      </span>
                    </div>
                    <p className="leading-relaxed text-foreground">{seg.text}</p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 py-12 text-center">
              <FileText className="mb-3 h-12 w-12 text-muted-foreground/60" />
              <p className="text-sm font-medium text-foreground">
                {status === 'processing' || status === 'queued'
                  ? 'Transcript is being generated'
                  : 'No transcript available'}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {status === 'processing' || status === 'queued'
                  ? 'Refresh the page in a moment to see it.'
                  : 'This call may not have produced a transcript.'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  if (s === 'processing' || s === 'queued') {
    return (
      <Badge
        variant="secondary"
        className="shrink-0 gap-1.5 bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30"
      >
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        {s === 'processing' ? 'Processing' : 'Queued'}
      </Badge>
    );
  }
  if (s === 'failed') {
    return <Badge variant="destructive" className="shrink-0">Failed</Badge>;
  }
  if (s === 'completed') {
    return (
      <Badge variant="default" className="shrink-0 bg-emerald-600 hover:bg-emerald-700">
        Completed
      </Badge>
    );
  }
  return <Badge variant="secondary" className="shrink-0">{status}</Badge>;
}
