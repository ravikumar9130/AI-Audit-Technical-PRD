'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, ChevronRight, Lightbulb } from 'lucide-react';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 5000;

function CallStatusBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  if (s === 'processing' || s === 'queued') {
    return (
      <Badge variant="secondary" className="gap-1.5 bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30">
        <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
        {s === 'processing' ? 'Processing' : 'Queued'}
      </Badge>
    );
  }
  if (s === 'failed') {
    return (
      <Badge variant="destructive">
        Failed
      </Badge>
    );
  }
  if (s === 'completed') {
    return <Badge variant="default">Completed</Badge>;
  }
  return <Badge variant="secondary">{status}</Badge>;
}

interface DashboardData {
  user: { first_name: string; last_name: string; role: string };
  metrics: {
    total_calls: number;
    avg_score: number;
    completed_calls: number;
    failed_calls: number;
    processing_calls: number;
  };
  recent_calls: Array<{
    call_id: number;
    status: string;
    overall_score?: number;
    created_at: string;
  }>;
  trend_data: Array<{ date: string; call_count: number; avg_score: number }>;
}


interface CoachingHint {
  callId: number;
  recommendation: string;
}

export default function AgentDashboard() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [coachingHint, setCoachingHint] = useState<CoachingHint | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchDashboard = useCallback(() => {
    if (!token) return Promise.resolve();
    return api.dashboard.getAgent(token).then(setData).catch(console.error);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    fetchDashboard().finally(() => setIsLoading(false));
  }, [token, fetchDashboard]);

  useEffect(() => {
    if (!token || !data || (data.metrics.processing_calls || 0) <= 0) return;
    const id = setInterval(fetchDashboard, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [token, data?.metrics.processing_calls, fetchDashboard]);

  useEffect(() => {
    if (!token || !data?.recent_calls?.length) return;
    const completed = data.recent_calls.find((c) => c.status === 'completed');
    if (!completed) return;
    api.calls
      .getResults(token, completed.call_id)
      .then((r: { recommendations?: string[] }) => {
        const recs = r?.recommendations;
        if (recs?.length) setCoachingHint({ callId: completed.call_id, recommendation: recs[0] });
      })
      .catch(() => {});
  }, [token, data?.recent_calls]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center text-muted-foreground">
        Error loading dashboard
      </div>
    );
  }

  const processingCount = Number(data.metrics.processing_calls) || 0;

  type MetricItem = { label: string; value: string; sub?: boolean; delay: string; destructive?: boolean };
  const metrics: MetricItem[] = [
    { label: 'Total Calls', value: (Number(data.metrics.total_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-1' },
    { label: 'Average Score', value: (Number(data.metrics.avg_score) || 0).toFixed(1), sub: true, delay: 'stagger-2' },
    { label: 'Completed', value: (Number(data.metrics.completed_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-3' },
    { label: 'Processing', value: processingCount.toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-4' },
    { label: 'Failed', value: (Number(data.metrics.failed_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-5', destructive: true },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-1 animate-fade-in-up stagger-1">
        <h1 className="text-3xl font-semibold tracking-tight">Agent Cockpit</h1>
        <p className="text-muted-foreground">
          Welcome back, {data.user.first_name} {data.user.last_name}
        </p>
      </div>

      {processingCount > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
          <span>
            <strong>{processingCount}</strong> call{processingCount !== 1 ? 's' : ''} being processed. This page updates automatically.
          </span>
        </div>
      )}

      {coachingHint && (
        <Card className="overflow-hidden border-amber-200/50 bg-gradient-to-r from-amber-50/80 to-transparent dark:border-amber-900/30 dark:from-amber-950/20">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20">
                <Lightbulb className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </span>
              <div>
                <p className="font-medium text-foreground">Next best action</p>
                <p className="text-sm text-muted-foreground">{coachingHint.recommendation}</p>
              </div>
            </div>
            <Button asChild variant="secondary" size="sm" className="shrink-0 gap-1">
              <Link href={`/dashboard/calls/${coachingHint.callId}`}>
                View transcript & hints
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {metrics.map((m, i) => (
          <Card
            key={m.label}
            className={cn(
              'animate-fade-in-up transition-all duration-300 hover:shadow-md hover:-translate-y-0.5',
              m.destructive && 'border-rose-200 dark:border-rose-900/50',
              m.delay
            )}
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{m.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={cn(
                  'text-2xl font-semibold tracking-tight tabular-nums',
                  m.destructive && 'text-rose-600 dark:text-rose-400'
                )}
              >
                {m.value}
              </div>
              {m.sub && (
                <Progress value={data.metrics.avg_score} className="mt-3 h-2 w-full" />
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="animate-fade-in-up stagger-5 transition-all duration-300 hover:shadow-md">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Recent Calls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.recent_calls.map((call, i) => (
              <Link
                key={call.call_id}
                href={`/dashboard/calls/${call.call_id}`}
                className={cn(
                  'flex items-center justify-between rounded-xl border border-border/80 bg-muted/30 px-4 py-3 transition-all hover:bg-muted/50 hover:border-primary/20 hover:shadow-sm animate-fade-in-up',
                  `stagger-${Math.min(i + 6, 10)}`
                )}
              >
                <div>
                  <p className="font-medium">Call #{call.call_id}</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(call.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  {call.overall_score !== undefined && (
                    <div className="text-right">
                      <p
                        className={cn(
                          'text-2xl font-semibold tabular-nums',
                          call.overall_score >= 80 && 'text-emerald-600 dark:text-emerald-400',
                          call.overall_score >= 60 && call.overall_score < 80 && 'text-amber-600 dark:text-amber-400',
                          call.overall_score < 60 && 'text-rose-600 dark:text-rose-400'
                        )}
                      >
                        {call.overall_score.toFixed(0)}
                      </p>
                      <Progress value={call.overall_score} className="mt-1 h-1.5 w-20" />
                    </div>
                  )}
                  <CallStatusBadge status={call.status} />
                  <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden />
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
