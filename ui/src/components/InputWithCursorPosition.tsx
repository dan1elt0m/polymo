import React from "react";

/**
 * A custom input component that preserves cursor position when typing
 * This solves the issue where the cursor jumps to the beginning or end
 * when typing in controlled React inputs.
 */
export const InputWithCursorPosition = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { onValueChange?: (value: string) => void }
>(({ value, onChange, onValueChange, ...props }, ref) => {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [selectionStart, setSelectionStart] = React.useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = React.useState<number | null>(null);

  // Forward the ref
  React.useImperativeHandle(ref, () => inputRef.current!, []);

  // Store current cursor position before the component updates
  const saveSelection = React.useCallback(() => {
    if (inputRef.current) {
      setSelectionStart(inputRef.current.selectionStart);
      setSelectionEnd(inputRef.current.selectionEnd);
    }
  }, []);

  // Save cursor position on every keystroke and focus
  React.useEffect(() => {
    const input = inputRef.current;
    if (!input) {
      return () => {}; // always return a cleanup function for all code paths
    }
    const handler = () => saveSelection();
    input.addEventListener("keyup", handler);
    input.addEventListener("mouseup", handler);
    input.addEventListener("focus", handler);
    return () => {
      input.removeEventListener("keyup", handler);
      input.removeEventListener("mouseup", handler);
      input.removeEventListener("focus", handler);
    };
  }, [saveSelection]);

  // Restore cursor position after render
  React.useEffect(() => {
    const input = inputRef.current;
    if (input && selectionStart !== null && selectionEnd !== null) {
      // Use setTimeout to ensure this happens after React's render cycle
      setTimeout(() => {
        if (document.activeElement === input) {
          try {
            input.setSelectionRange(selectionStart, selectionEnd);
          } catch (e) {
            // Ignore errors that might occur if input is no longer in the DOM
          }
        }
      }, 0);
    }
  }, [value, selectionStart, selectionEnd]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Save cursor position
    setSelectionStart(e.target.selectionStart);
    setSelectionEnd(e.target.selectionEnd);

    // Call original onChange if provided
    if (onChange) {
      onChange(e);
    }

    // Call onValueChange with the new value if provided
    if (onValueChange) {
      onValueChange(e.target.value);
    }
  };

  return <input ref={inputRef} value={value} onChange={handleChange} {...props} />;
});

InputWithCursorPosition.displayName = "InputWithCursorPosition";
