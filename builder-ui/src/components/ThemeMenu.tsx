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
        className="rounded-full border border-border dark:border-drac-border px-3 py-2 text-xs font-medium text-slate-11 dark:text-drac-foreground hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent transition-colors"
      >
        {label}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-48 overflow-hidden rounded-lg border border-border/70 bg-background shadow-lg dark:bg-drac-surface dark:border-drac-border z-50"
        >
          {(['light','dark','system'] as ThemeMode[]).map(opt => {
            const active = opt === mode;
            return (
              <button
                key={opt}
                role="menuitemradio"
                aria-checked={active}
                onClick={() => { onChange(opt); setOpen(false); }}
                className={`flex w-full items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${active ? 'bg-blue-9 text-white dark:bg-drac-accent dark:text-drac-foreground' : 'hover:bg-slate-3 dark:hover:bg-drac-base/60 text-slate-12 dark:text-drac-foreground'} focus-visible:outline-none focus-visible:bg-blue-9 focus-visible:text-white dark:focus-visible:bg-drac-accent`}
              >
                <span className="inline-block h-2 w-2 rounded-full border border-border dark:border-drac-border" style={active ? { background: 'currentColor' } : {}} />
                {opt === 'system' ? 'System (auto)' : opt.charAt(0).toUpperCase() + opt.slice(1)}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

