import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

import { cx } from "../../lib/cx";
import styles from "./Button.module.css";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  /** Shows `pendingLabel` and disables the button while an action runs. */
  pending?: boolean;
  pendingLabel?: string;
  icon?: ReactNode;
  block?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  variant = "secondary",
  size = "md",
  pending = false,
  pendingLabel,
  icon,
  block = false,
  type = "button",
  disabled,
  children,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(styles.button, className)}
      data-variant={variant}
      data-size={size}
      data-block={block || undefined}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      {...rest}
    >
      {icon ? <span className={styles.icon}>{icon}</span> : null}
      <span>{pending && pendingLabel ? pendingLabel : children}</span>
    </button>
  );
}
