import React from "react";

interface InfoTooltipProps {
  text: string;
  className?: string;
}

export const InfoTooltip: React.FC<InfoTooltipProps> = ({ text, className = "" }) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLSpanElement | null>(null);

  const toggle = React.useCallback(() => setOpen(o => !o), []);
  const close = React.useCallback(() => setOpen(false), []);

  React.useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        close();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('mousedown', handleClick);
    window.addEventListener('keydown', handleKey);
    return () => {
      window.removeEventListener('mousedown', handleClick);
      window.removeEventListener('keydown', handleKey);
    };
  }, [open, close]);

  return (
    <span ref={ref} className={`relative inline-flex ${className}`}>
      <button
        type="button"
        aria-label="Info"
        aria-expanded={open}
        onClick={toggle}
        className="flex h-4 w-4 items-center justify-center rounded-full border border-border/60 bg-background text-[10px] font-semibold text-slate-11 dark:bg-drac-base dark:border-drac-border dark:text-drac-foreground cursor-pointer select-none transition-colors hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-1/2 top-full z-50 w-60 -translate-x-1/2 translate-y-2 rounded-md border border-border/70 bg-slate-12 px-3 py-2 text-xs font-medium leading-relaxed text-white shadow-xl dark:bg-drac-surface dark:border-drac-border dark:text-drac-foreground dark:shadow-[0_8px_24px_-6px_rgba(0,0,0,0.7)] animate-fade-in"
        >
          {text}
        </span>
      )}
    </span>
  );
};
