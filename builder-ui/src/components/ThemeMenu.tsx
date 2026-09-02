import React from "react";

export type ThemeMode = 'light' | 'dark' | 'system';

interface ThemeMenuProps {
  mode: ThemeMode;
  effective: 'light' | 'dark';
  onChange: (mode: ThemeMode) => void;
}

export const ThemeMenu: React.FC<ThemeMenuProps> = ({ mode, effective, onChange }) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('mousedown', handler);
    window.addEventListener('keydown', key);
    return () => { window.removeEventListener('mousedown', handler); window.removeEventListener('keydown', key); };
  }, [open]);

  const label = mode === 'system' ? `System (${effective})` : mode.charAt(0).toUpperCase() + mode.slice(1);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-xs font-medium text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
      >
        <span aria-hidden="true" className="text-[13px] leading-none">{effective === 'dark' ? '☾' : '☀'}</span>
        {label}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1.5 w-44 overflow-hidden rounded-md border border-border bg-surface p-1 shadow-card"
        >
          {(['light','dark','system'] as ThemeMode[]).map(opt => {
            const active = opt === mode;
            return (
              <button
                key={opt}
                role="menuitemradio"
                aria-checked={active}
                onClick={() => { onChange(opt); setOpen(false); }}
                className={`flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-sm transition-colors ${active ? 'bg-accent text-accent-fg' : 'text-fg hover:bg-raised'} focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:bg-raised`}
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full border border-current" style={active ? { background: 'currentColor' } : {}} />
                {opt === 'system' ? 'System (auto)' : opt.charAt(0).toUpperCase() + opt.slice(1)}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
