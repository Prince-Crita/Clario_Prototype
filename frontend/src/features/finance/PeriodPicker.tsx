/**
 * The period control (plan §27.8): compact trigger that always shows the selected period, a small
 * panel with presets and a custom month range. It states what it changes: the monthly charts and
 * tables; headline figures keep the period printed on each.
 */
import { CalendarRange, Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "../../design-system";
import { PRESETS, recentMonths, type Period, type PeriodKey } from "./period";
import styles from "./PeriodPicker.module.css";

interface PeriodPickerProps {
  period: Period;
  today: Date;
  onChange: (key: PeriodKey, custom?: { from: string; to: string }) => void;
}

export function PeriodPicker({ period, today, onChange }: PeriodPickerProps) {
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(period.from ?? "");
  const [to, setTo] = useState(period.to ?? "");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const months = recentMonths(today);

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);

  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };
  const choose = (key: PeriodKey) => {
    onChange(key);
    close();
  };
  const customValid = Boolean(from && to && from <= to);

  return (
    <div
      ref={root}
      className={styles.root}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          close();
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`Period: ${period.name}, ${period.range}. Change period`}
        onClick={() => {
          setFrom(period.from ?? months[5]?.key ?? "");
          setTo(period.to ?? months[0]?.key ?? "");
          setOpen((v) => !v);
        }}
      >
        <CalendarRange size={15} aria-hidden="true" className={styles.icon} />
        <span className={styles.name}>{period.name}</span>
        {period.from ? <span className={styles.range}>{period.range}</span> : null}
        <ChevronDown size={14} aria-hidden="true" className={styles.icon} />
      </button>
      {open ? (
        <div id={id} role="dialog" aria-label="Choose a period" className={styles.panel}>
          <ul className={styles.presets}>
            {PRESETS.map((p) => (
              <li key={p.key}>
                <button
                  type="button"
                  className={styles.preset}
                  aria-pressed={period.key === p.key}
                  autoFocus={period.key === p.key}
                  onClick={() => choose(p.key)}
                >
                  {p.name}
                  {period.key === p.key ? <Check size={14} aria-hidden="true" /> : null}
                </button>
              </li>
            ))}
          </ul>
          <fieldset className={styles.custom}>
            <legend>Custom months</legend>
            <label>
              <span>From</span>
              <select value={from} onChange={(e) => setFrom(e.target.value)}>
                {months.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>To</span>
              <select value={to} onChange={(e) => setTo(e.target.value)}>
                {months.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <Button
              size="sm"
              variant="primary"
              disabled={!customValid}
              onClick={() => {
                onChange("custom", { from, to });
                close();
              }}
            >
              Apply
            </Button>
          </fieldset>
          <p className={styles.note}>
            Charts and monthly tables follow this period. Headline figures keep the period shown on
            each one.
          </p>
        </div>
      ) : null}
    </div>
  );
}
