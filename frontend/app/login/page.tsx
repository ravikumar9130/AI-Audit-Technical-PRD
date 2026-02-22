'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Mic } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background px-4">
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom_right,hsl(var(--muted))_0%,hsl(var(--background))_50%,hsl(var(--muted)/0.5)_100%)]" />
      <div
        className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }}
      />

      <Card className="w-full max-w-md relative animate-fade-in-up stagger-1 border-border/80 bg-card/95 dark:bg-card/90 backdrop-blur-xl shadow-xl">
        <CardHeader className="space-y-3 pb-2">
          <div className="flex justify-center animate-fade-in-up stagger-2">
            <div className="rounded-2xl bg-primary/10 p-3">
              <Mic className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-semibold tracking-tight text-center animate-fade-in-up stagger-3">
            Audit AI
          </CardTitle>
          <CardDescription className="text-center text-muted-foreground animate-fade-in-up stagger-4">
            Enterprise Speech Intelligence Platform
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4 animate-fade-in-up stagger-5">
            {error && (
              <Alert variant="destructive" className="animate-scale-in">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="email" className="text-muted-foreground">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="transition-all duration-200 focus:border-primary/50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-muted-foreground">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="transition-all duration-200 focus:border-primary/50"
              />
            </div>
          </CardContent>
          <CardFooter className="animate-fade-in-up stagger-6">
            <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign in
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
