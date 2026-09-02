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
        onClick={(e) => { e.preventDefault(); toggle(); }}
        className="flex h-3.5 w-3.5 items-center justify-center rounded-full border border-border-strong/70 bg-transparent text-[9px] font-semibold leading-none text-fg-muted cursor-pointer select-none transition-colors hover:border-accent hover:text-accent-text"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-1/2 top-full z-50 w-64 -translate-x-1/2 translate-y-2 rounded-md border border-border bg-fg px-3 py-2 text-xs font-normal leading-relaxed text-background shadow-xl dark:bg-raised dark:text-fg"
        >
          {text}
        </span>
      )}
    </span>
  );
};
