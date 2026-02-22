'use client';

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, UploadCloud, FileAudio, Archive, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

const MAX_SINGLE_MB = 500;
const MAX_BULK_MB = 2500;
const ALLOWED_AUDIO_EXT = ['.wav', '.mp3', '.mp4', '.m4a', '.flac', '.ogg', '.webm'];
const ACCEPT_AUDIO = ALLOWED_AUDIO_EXT.join(',');

interface Template {
  template_id: number;
  name: string;
  vertical: string;
  is_active?: boolean;
}

function getFileExtension(name: string): string {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function UploadPage() {
  const { token } = useAuth();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | ''>('');
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploadingSingle, setUploadingSingle] = useState(false);
  const [uploadingBulk, setUploadingBulk] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const singleInputRef = useRef<HTMLInputElement>(null);
  const bulkInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!token) return;
    api.templates
      .list(token)
      .then((data: Template[]) => {
        setTemplates(data);
        if (data.length > 0 && selectedTemplateId === '') {
          setSelectedTemplateId(data[0].template_id);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  const clearFeedback = () => {
    setSuccess(null);
    setError(null);
  };

  const validateSingle = (file: File): string | null => {
    const ext = getFileExtension(file.name);
    if (!ALLOWED_AUDIO_EXT.includes(ext)) {
      return `Invalid format. Allowed: ${ALLOWED_AUDIO_EXT.join(', ')}`;
    }
    const maxBytes = MAX_SINGLE_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      return `File too large. Max ${MAX_SINGLE_MB} MB (${formatBytes(file.size)} selected).`;
    }
    return null;
  };

  const validateBulk = (file: File): string | null => {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      return 'Bulk upload must be a ZIP file.';
    }
    const maxBytes = MAX_BULK_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      return `ZIP too large. Max ${MAX_BULK_MB} MB (${formatBytes(file.size)} selected).`;
    }
    return null;
  };

  const handleSingleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    clearFeedback();
    const file = e.target.files?.[0];
    if (!file) {
      setSingleFile(null);
      return;
    }
    const err = validateSingle(file);
    if (err) {
      setError(err);
      setSingleFile(null);
      e.target.value = '';
      return;
    }
    setSingleFile(file);
  };

  const handleBulkChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    clearFeedback();
    const file = e.target.files?.[0];
    if (!file) {
      setBulkFile(null);
      return;
    }
    const err = validateBulk(file);
    if (err) {
      setError(err);
      setBulkFile(null);
      e.target.value = '';
      return;
    }
    setBulkFile(file);
  };

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || selectedTemplateId === '' || !singleFile) return;
    clearFeedback();
    setUploadingSingle(true);
    try {
      const res = await api.upload.single(token, singleFile, Number(selectedTemplateId));
      setSuccess(`Call #${res.call_id} queued for processing. Check the Agent dashboard for live status. ${res.message || ''}`);
      setSingleFile(null);
      if (singleInputRef.current) singleInputRef.current.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploadingSingle(false);
    }
  };

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || selectedTemplateId === '' || !bulkFile) return;
    clearFeedback();
    setUploadingBulk(true);
    try {
      const res = await api.upload.bulk(token, bulkFile, Number(selectedTemplateId));
      setSuccess(
        `Batch ${res.batch_id}: ${res.num_files} file(s) queued. Check the Agent dashboard for live status. ${res.message || ''}`
      );
      setBulkFile(null);
      if (bulkInputRef.current) bulkInputRef.current.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk upload failed');
    } finally {
      setUploadingBulk(false);
    }
  };

  const templateId = selectedTemplateId === '' ? 0 : Number(selectedTemplateId);
  const canSingle = templateId > 0 && singleFile && !uploadingSingle && !uploadingBulk;
  const canBulk = templateId > 0 && bulkFile && !uploadingSingle && !uploadingBulk;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upload calls</h1>
        <p className="text-muted-foreground mt-1">
          Upload audio files for transcription and scoring. Choose a scoring template, then upload a
          single file or a ZIP of multiple files.
        </p>
      </div>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="border-green-500/50 bg-green-500/5">
          <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          <AlertTitle>Success</AlertTitle>
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {templates.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center py-6">
              No scoring templates available. Ask an admin or manager to create a template first.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="template">Scoring template</Label>
            <select
              id="template"
              value={selectedTemplateId}
              onChange={(e) => {
                clearFeedback();
                setSelectedTemplateId(e.target.value === '' ? '' : Number(e.target.value));
              }}
              className={cn(
                'flex h-11 w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm',
                'ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
              )}
              aria-describedby="template-description"
            >
              {templates.map((t) => (
                <option key={t.template_id} value={t.template_id}>
                  {t.name} ({t.vertical})
                </option>
              ))}
            </select>
            <p id="template-description" className="text-xs text-muted-foreground">
              Template defines the scoring criteria and vertical (e.g. Sales, Support).
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileAudio className="h-5 w-5" />
                  Single file
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  WAV, MP3, MP4, M4A, FLAC, OGG, WebM. Max {MAX_SINGLE_MB} MB.
                </p>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSingleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="single-file">Audio file</Label>
                    <Input
                      id="single-file"
                      ref={singleInputRef}
                      type="file"
                      accept={ACCEPT_AUDIO}
                      onChange={handleSingleChange}
                      disabled={uploadingSingle || uploadingBulk}
                      className="cursor-pointer"
                    />
                    {singleFile && (
                      <p className="text-xs text-muted-foreground">
                        {singleFile.name} ({formatBytes(singleFile.size)})
                      </p>
                    )}
                  </div>
                  <Button type="submit" disabled={!canSingle} className="w-full">
                    {uploadingSingle ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Uploading…
                      </>
                    ) : (
                      <>
                        <UploadCloud className="mr-2 h-4 w-4" />
                        Upload single file
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Archive className="h-5 w-5" />
                  Bulk (ZIP)
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  ZIP containing audio files. Max {MAX_BULK_MB} MB.
                </p>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleBulkSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="bulk-file">ZIP file</Label>
                    <Input
                      id="bulk-file"
                      ref={bulkInputRef}
                      type="file"
                      accept=".zip"
                      onChange={handleBulkChange}
                      disabled={uploadingSingle || uploadingBulk}
                      className="cursor-pointer"
                    />
                    {bulkFile && (
                      <p className="text-xs text-muted-foreground">
                        {bulkFile.name} ({formatBytes(bulkFile.size)})
                      </p>
                    )}
                  </div>
                  <Button type="submit" disabled={!canBulk} variant="secondary" className="w-full">
                    {uploadingBulk ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Uploading…
                      </>
                    ) : (
                      <>
                        <UploadCloud className="mr-2 h-4 w-4" />
                        Upload bulk (ZIP)
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" asChild>
              <Link href="/dashboard/agent">View calls (Cockpit)</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard/manager">War Room</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard/cxo">Executive dashboard</Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
