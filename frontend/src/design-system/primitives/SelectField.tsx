import { forwardRef, useId, type SelectHTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import fieldStyles from "./TextField.module.css";
import styles from "./SelectField.module.css";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  hint?: string;
  options: SelectOption[];
}

/** Native select (keyboard, mobile pickers and screen readers for free), styled like TextField. */
export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, hint, options, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <div className={cx(fieldStyles.field, className)}>
      <label className={fieldStyles.label} htmlFor={id}>
        {label}
      </label>
      <select
        ref={ref}
        id={id}
        className={cx(fieldStyles.input, styles.select)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? (
        <p id={`${id}-hint`} className={fieldStyles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
});
