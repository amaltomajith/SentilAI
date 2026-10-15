import { useEffect, useState } from 'react';
import { fetchBlobUrl } from '@/lib/api';

/** Shows an image or voice note the agent sent, loaded through the authenticated media route. */
export function MediaAttachment({ kind, sha256 }: { kind: 'image' | 'voice'; sha256: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true, made: string | null = null;
    fetchBlobUrl(`/api/media/${sha256}`).then((u) => { made = u; if (live) setUrl(u); }).catch(() => live && setFailed(true));
    return () => { live = false; if (made) URL.revokeObjectURL(made); };
  }, [sha256]);
  if (failed) return <p className="mt-2 font-mono text-[11px] text-faint">[{kind} sent, file no longer available]</p>;
  if (!url) return <div className="mt-3 h-40 w-28 animate-pulse rounded-sm bg-surface-3" />;
  return kind === 'image'
    ? <a href={url} target="_blank" rel="noreferrer" className="mt-3 block w-fit overflow-hidden rounded-sm border border-line-strong"><img src={url} alt="What the scammer received" className="max-h-80 w-auto" /></a>
    : <audio controls src={url} className="mt-3 w-full max-w-xs" />;
}