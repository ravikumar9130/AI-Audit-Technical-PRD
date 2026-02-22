'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Loader2, AlertTriangle, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DashboardData {
  user: { first_name: string; last_name: string; role: string };
  team_metrics: {
    total_calls: number;
    avg_score: number;
    completed_calls: number;
    failed_calls: number;
    processing_calls: number;
  };
  team_members: Array<{ user_id: number; first_name: string; last_name: string }>;
  calls_by_agent: Array<{
    agent_id: number;
    agent_name: string;
    total_calls: number;
    avg_score: number;
    completed_calls: number;
  }>;
  risk_alerts: Array<{ call_id: number; agent_id: number; score: number; type: string; message: string }>;
  skill_heatmap: Record<string, Record<string, number>>;
}

export default function ManagerDashboard() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.dashboard.getManager(token).then(setData).catch(console.error).finally(() => setIsLoading(false));
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

  const metrics = [
    { label: 'Total Calls', value: (Number(data.team_metrics.total_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-1' },
    { label: 'Team Avg Score', value: (Number(data.team_metrics.avg_score) || 0).toFixed(1), delay: 'stagger-2' },
    { label: 'Completed', value: (Number(data.team_metrics.completed_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-3' },
    { label: 'Processing', value: (Number(data.team_metrics.processing_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-4' },
    { label: 'Failed', value: (Number(data.team_metrics.failed_calls) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }), delay: 'stagger-5', destructive: true },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-1 animate-fade-in-up stagger-1">
        <h1 className="text-3xl font-semibold tracking-tight">Team War Room</h1>
        <p className="text-muted-foreground">
          Welcome back, {data.user.first_name} {data.user.last_name}
        </p>
      </div>

      {data.risk_alerts.length > 0 && (
        <div className="space-y-2 animate-fade-in-up stagger-2">
          <h2 className="text-lg font-medium flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Risk Alerts
          </h2>
          {data.risk_alerts.map((alert, index) => (
            <Alert
              key={index}
              variant={alert.type === 'compliance_violation' ? 'destructive' : 'default'}
              className="animate-scale-in flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <AlertTitle>
                  {alert.type === 'compliance_violation' ? 'Compliance Violation' : 'Low Score Alert'}
                </AlertTitle>
                <AlertDescription>
                  Call #{alert.call_id}: {alert.message}
                </AlertDescription>
              </div>
              <Button asChild variant={alert.type === 'compliance_violation' ? 'outline' : 'secondary'} size="sm" className="shrink-0 gap-1.5">
                <Link href={`/dashboard/calls/${alert.call_id}`}>
                  <FileText className="h-3.5 w-3.5" />
                  View transcript
                </Link>
              </Button>
            </Alert>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {metrics.map((m) => (
          <Card
            key={m.label}
            className={cn(
              'animate-fade-in-up transition-all duration-300 hover:shadow-md hover:-translate-y-0.5',
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
                  m.destructive && 'text-destructive'
                )}
              >
                {m.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="animate-fade-in-up stagger-6 transition-all duration-300 hover:shadow-md">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Team Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {data.calls_by_agent.map((agent, i) => (
              <div
                key={agent.agent_id}
                className={cn(
                  'flex items-center justify-between rounded-xl border border-border/80 bg-muted/30 px-4 py-3 transition-colors hover:bg-muted/50 animate-fade-in-up',
                  `stagger-${Math.min(i + 7, 10)}`
                )}
              >
                <div>
                  <p className="font-medium">{agent.agent_name}</p>
                  <p className="text-sm text-muted-foreground">
                    {agent.completed_calls} calls completed
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-semibold tabular-nums">{agent.avg_score.toFixed(1)}</p>
                  <p className="text-xs text-muted-foreground">avg score</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
