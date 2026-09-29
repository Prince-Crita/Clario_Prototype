import { forwardRef, useEffect, useId, useImperativeHandle, useRef, type FormEvent } from "react";

import { Button } from "../../design-system";
import styles from "./AssistantPanel.module.css";

export const MAX_CHARS = 4000;
const SHOW_COUNT_FROM = 3500;
const COUNT = new Intl.NumberFormat("en-IN");

interface ComposerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  pending: boolean;
  disabled: boolean;
  placeholder?: string | undefined;
}

/** Enter sends; Shift+Enter starts a new line. The box grows with the question. */
export const Composer = forwardRef<HTMLTextAreaElement, ComposerProps>(function Composer(
  { label, value, onChange, onSubmit, pending, disabled, placeholder },
  ref,
) {
  const id = useId();
  const box = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => box.current as HTMLTextAreaElement);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!pending && !disabled && value.trim()) onSubmit(value);
  };
  const showCount = value.length >= SHOW_COUNT_FROM;

  return (
    <form className={styles.composer} onSubmit={submit}>
      <label className="visually-hidden" htmlFor={id}>
        {label}
      </label>
      <textarea
        ref={box}
        id={id}
        className={styles.input}
        rows={1}
        value={value}
        maxLength={MAX_CHARS}
        placeholder={placeholder ?? "Ask about revenue, cash, receivables…"}
        disabled={disabled}
        aria-describedby={showCount ? `${id}-count` : undefined}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <div className={styles.composerFoot}>
        {showCount ? (
          <span id={`${id}-count`} className={styles.count}>
            {COUNT.format(value.length)} / {COUNT.format(MAX_CHARS)}
          </span>
        ) : (
          <span className={styles.hint}>Shift + Enter for a new line</span>
        )}
        <Button
          type="submit"
          variant="primary"
          size="sm"
          pending={pending}
          pendingLabel="Asking…"
          disabled={disabled || !value.trim()}
        >
          Ask
        </Button>
      </div>
    </form>
  );
});
