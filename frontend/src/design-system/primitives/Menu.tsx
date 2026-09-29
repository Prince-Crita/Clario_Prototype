/** Dropdown menu (Radix): keyboard, typeahead, focus management and escape handling built in. */
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { Check } from "lucide-react";
import type { ReactNode } from "react";

import styles from "./Menu.module.css";

interface MenuProps {
  trigger: ReactNode;
  label?: string;
  children: ReactNode;
  align?: "start" | "end";
  side?: "top" | "bottom";
}

export function Menu({ trigger, children, align = "start", side = "bottom" }: MenuProps) {
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild>{trigger}</Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content className={styles.content} align={align} side={side} sideOffset={6}>
          {children}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

interface MenuItemProps {
  children: ReactNode;
  onSelect?: () => void;
  selected?: boolean;
  tone?: "default" | "negative";
}

export function MenuItem({ children, onSelect, selected, tone = "default" }: MenuItemProps) {
  return (
    <Dropdown.Item
      className={styles.item}
      data-tone={tone}
      data-selected={selected || undefined}
      {...(onSelect ? { onSelect } : {})}
    >
      <span className={styles.itemText}>{children}</span>
      {selected ? <Check size={14} aria-label="Current" className={styles.check} /> : null}
    </Dropdown.Item>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <Dropdown.Label className={styles.label}>{children}</Dropdown.Label>;
}

export function MenuSeparator() {
  return <Dropdown.Separator className={styles.separator} />;
}
