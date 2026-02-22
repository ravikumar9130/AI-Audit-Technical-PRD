'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DashboardData {
  user: { first_name: string; last_name: string; role: string };
  company_metrics: {
    total_calls: number;
    avg_score: number;
    completed_calls: number;
    failed_calls: number;
    processing_calls: number;
  };
  vertical_breakdown: Record<
    string,
    { template_name: string; total_calls: number; avg_score: number; completion_rate: number }
  >;
  compliance_summary: { total_evaluated: number; violations: number; compliance_rate: number };
  top_issues: Array<{ issue: string; frequency: number; percentage: number }>;
}

export default function CXODashboard() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.dashboard.getCXO(token).then(setData).catch(console.error).finally(() => setIsLoading(false));
  }, [token]);

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

  const totalCalls = Number(data.company_metrics.total_calls) || 0;
  const completionRate =
    totalCalls > 0
      ? ((Number(data.company_metrics.completed_calls) || 0) / totalCalls * 100).toFixed(1)
      : '0';

  const kpis = [
    { label: 'Total Calls', value: totalCalls.toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-1' },
    { label: 'Company Avg Score', value: (Number(data.company_metrics.avg_score) || 0).toFixed(1), delay: 'stagger-2', progress: true },
    { label: 'Completion Rate', value: `${completionRate}%`, delay: 'stagger-3' },
    { label: 'Compliance Rate', value: `${(Number(data.compliance_summary.compliance_rate) || 0).toFixed(1)}%`, delay: 'stagger-4' },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-1 animate-fade-in-up stagger-1">
        <h1 className="text-3xl font-semibold tracking-tight">Executive Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {data.user.first_name} {data.user.last_name}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((k) => (
          <Card
            key={k.label}
            className={cn(
              'animate-fade-in-up transition-all duration-300 hover:shadow-md hover:-translate-y-0.5',
              k.delay
            )}
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{k.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold tracking-tight tabular-nums">{k.value}</div>
              {k.progress && (
                <Progress value={data.company_metrics.avg_score} className="mt-3 h-2 w-full" />
              )}
              {k.label === 'Compliance Rate' && data.compliance_summary.violations > 0 && (
                <p className="text-sm text-destructive mt-1">
                  {data.compliance_summary.violations} violations
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="animate-fade-in-up stagger-5 transition-all duration-300 hover:shadow-md">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Performance by Vertical</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              {Object.entries(data.vertical_breakdown).map(([vertical, metrics], i) => (
                <div
                  key={vertical}
                  className={cn(
                    'rounded-xl border border-border/80 bg-muted/30 p-4 transition-colors hover:bg-muted/50 animate-fade-in-up',
                    `stagger-${Math.min(i + 6, 10)}`
                  )}
                >
                  <h3 className="font-semibold mb-2">{vertical}</h3>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Calls</span>
                      <p className="font-medium tabular-nums">{(Number(metrics.total_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Avg Score</span>
                      <p className="font-medium tabular-nums">{(Number(metrics.avg_score) || 0).toFixed(1)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Completion</span>
                      <p className="font-medium tabular-nums">{(Number(metrics.completion_rate) || 0).toFixed(1)}%</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="animate-fade-in-up stagger-6 transition-all duration-300 hover:shadow-md">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Top Improvement Areas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.top_issues.map((issue, i) => (
                <div
                  key={i}
                  className={cn(
                    'flex items-center justify-between rounded-xl border border-border/80 bg-muted/30 px-4 py-3 transition-colors hover:bg-muted/50 animate-fade-in-up',
                    `stagger-${Math.min(i + 7, 10)}`
                  )}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-semibold text-muted-foreground tabular-nums">
                      #{i + 1}
                    </span>
                    <p className="font-medium">{issue.issue}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold tabular-nums">{issue.frequency}</p>
                    <p className="text-xs text-muted-foreground">{issue.percentage.toFixed(1)}% of calls</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
