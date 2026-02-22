'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Mic, LayoutDashboard, Users, BarChart3, LogOut, Loader2, UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils';

const roleNav: Record<string, { href: string; label: string; icon: React.ElementType }[]> = {
  Agent: [
    { href: '/dashboard/agent', label: 'Cockpit', icon: LayoutDashboard },
    { href: '/dashboard/upload', label: 'Upload', icon: UploadCloud },
  ],
  Manager: [
    { href: '/dashboard/manager', label: 'War Room', icon: LayoutDashboard },
    { href: '/dashboard/upload', label: 'Upload', icon: UploadCloud },
  ],
  CXO: [
    { href: '/dashboard/cxo', label: 'Executive', icon: BarChart3 },
    { href: '/dashboard/upload', label: 'Upload', icon: UploadCloud },
  ],
  Admin: [
    { href: '/dashboard/cxo', label: 'Executive', icon: BarChart3 },
    { href: '/dashboard/agent', label: 'Agent', icon: LayoutDashboard },
    { href: '/dashboard/manager', label: 'Manager', icon: Users },
    { href: '/dashboard/upload', label: 'Upload', icon: UploadCloud },
  ],
};

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isLoading } = useAuth();
  const links = user ? roleNav[user.role] ?? roleNav.Agent : [];

  useEffect(() => {
    if (!isLoading && !user) router.replace('/login');
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-50 w-full border-b border-border/80 bg-card/80 backdrop-blur-xl transition-all duration-300">
        <div className="container flex h-14 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <div className="rounded-lg bg-primary/10 p-1.5 transition-transform duration-200 hover:scale-105">
              <Mic className="h-5 w-5 text-primary" />
            </div>
            <span className="hidden sm:inline">Audit AI</span>
          </Link>
          <nav className="flex items-center gap-1">
            {links.map((item, i) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 animate-fade-in-up',
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                  style={{ animationDelay: `${(i + 1) * 50}ms` }}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground hidden sm:inline">
              {user?.first_name} {user?.last_name}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              className="rounded-xl transition-colors hover:bg-destructive/10 hover:text-destructive"
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>
      <main className="flex-1 container py-6 px-4">{children}</main>
    </div>
  );
}
