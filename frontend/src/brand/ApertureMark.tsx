/**
 * The Clario "Aperture" mark (plan §28.1): an open ring (280°) with a lime disc in its opening —
 * a lens / point of clarity. Geometry on a 32-unit grid, ring centre (16,16), radius 10.5:
 *   arc from 85° to 5° (maths angles) the long way round, disc centred at 45° in the gap.
 * Deliberately unlike Crita's squared, teardrop "C".
 */
import type { SVGProps } from "react";

export const APERTURE_RING_PATH = "M16.915 5.54A10.5 10.5 0 1 0 26.46 15.085";

interface ApertureMarkProps extends Omit<SVGProps<SVGSVGElement>, "children"> {
  size?: number;
  /** "default" = forest ring on light; "inverse" = white ring on forest. */
  tone?: "default" | "inverse";
  title?: string;
}

export function ApertureMark({ size = 28, tone = "default", title, ...rest }: ApertureMarkProps) {
  const ring = tone === "inverse" ? "var(--ink-inverse)" : "var(--forest)";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      <path
        d={APERTURE_RING_PATH}
        fill="none"
        stroke={ring}
        strokeWidth={4}
        strokeLinecap="round"
      />
      <circle cx={23.425} cy={8.575} r={2.6} fill="var(--lime)" />
    </svg>
  );
}
