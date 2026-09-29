/** Loading placeholder in the exact shape of the content — no spinners for page content (§27.3). */
import type { CSSProperties } from "react";

import styles from "./Skeleton.module.css";

interface SkeletonProps {
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  radius?: "sm" | "md";
}

export function Skeleton({ width = "100%", height = "1em", radius = "sm" }: SkeletonProps) {
  return (
    <span
      className={styles.skeleton}
      data-radius={radius}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}
