/**
 * Ask Clario on the page itself (plan §27.10): the intelligence belongs to the page, not to a
 * widget in a corner.
 *   "card"  — on the Overview, beside Signals: the question box and this page's prompts as rows.
 *   "strip" — on the other pages, one line under the page header.
 * Typing and pressing Ask sends the question (the user asked); a suggested prompt only places it
 * in the panel's box.
 */
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { ApertureMark } from "../../brand/ApertureMark";
import styles from "./AskBar.module.css";

interface AskBarProps {
  organisation: string;
  prompts: string[];
  /** Open Ask Clario with `question`; `send` asks it straight away. */
  onAsk: (question: string, send: boolean) => void;
  variant?: "card" | "strip";
}

export function AskBar({ organisation, prompts, onAsk, variant = "strip" }: AskBarProps) {
  const [text, setText] = useState("");
  const id = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const question = text.trim();
    if (!question) return;
    onAsk(question, true);
    setText("");
  };
  const form = (
    <form className={styles.form} onSubmit={submit} role="search" aria-label="Ask Clario">
      <label htmlFor={id} className="visually-hidden">
        Ask Clario a question
      </label>
      <input
        id={id}
        className={styles.input}
        value={text}
        maxLength={4000}
        autoComplete="off"
        placeholder={
          variant === "card"
            ? "Ask anything about your finances…"
            : `Ask Clario about ${organisation}…`
        }
        onChange={(event) => setText(event.target.value)}
      />
      <button type="submit" className={styles.go} disabled={!text.trim()} aria-label="Ask">
        <ArrowRight size={16} aria-hidden="true" />
      </button>
    </form>
  );

  if (variant === "card") {
    return (
      <aside className={styles.card} aria-label="Ask Clario about these figures">
        <div className={styles.cardHead}>
          <span className={styles.cardMark} aria-hidden="true">
            <ApertureMark size={20} tone="inverse" />
          </span>
          <div>
            <p className={styles.cardTitle}>Ask Clario</p>
            <p className={styles.cardSub}>Answers from {organisation}'s own books.</p>
          </div>
        </div>
        {form}
        <ul className={styles.promptRows}>
          {prompts.map((prompt) => (
            <li key={prompt}>
              <button
                type="button"
                className={styles.promptRow}
                onClick={() => onAsk(prompt, false)}
              >
                <span>{prompt}</span>
                <ArrowUpRight size={15} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      </aside>
    );
  }

  return (
    <div className={styles.strip}>
      <span className={styles.stripMark} aria-hidden="true">
        <ApertureMark size={18} />
      </span>
      {form}
      <p className={styles.prompts}>
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className={styles.prompt}
            onClick={() => onAsk(prompt, false)}
          >
            {prompt}
          </button>
        ))}
      </p>
    </div>
  );
}
