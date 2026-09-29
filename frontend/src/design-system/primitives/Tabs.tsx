/** Text tabs with a 2-px lime underline on the active tab (plan §27.3). Radix handles a11y/keys. */
import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

import styles from "./Tabs.module.css";

interface TabsProps {
  label: string;
  tabs: { value: string; label: string; content: ReactNode }[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}

export function Tabs({ label, tabs, value, defaultValue, onValueChange }: TabsProps) {
  return (
    <RadixTabs.Root
      className={styles.root}
      {...(value !== undefined ? { value } : {})}
      {...(value === undefined ? { defaultValue: defaultValue ?? tabs[0]?.value ?? "" } : {})}
      {...(onValueChange ? { onValueChange } : {})}
    >
      <RadixTabs.List className={styles.list} aria-label={label}>
        {tabs.map((t) => (
          <RadixTabs.Trigger key={t.value} value={t.value} className={styles.trigger}>
            {t.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {tabs.map((t) => (
        <RadixTabs.Content key={t.value} value={t.value} className={styles.content}>
          {t.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
