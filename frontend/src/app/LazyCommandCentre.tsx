/**
 * The Command Centre (and its charts) loads on first visit, not with the app shell (plan §30).
 * Loaded with `lazyComponent` (no Suspense, so no 300 ms fallback hold), and fetched at boot on
 * dashboard URLs, in parallel with the session request.
 */
import { Skeleton } from "../design-system";
import { lazyComponent } from "../lib/lazyComponent";

export const LazyCommandCentre = lazyComponent(
  () => import("../features/finance/CommandCentre"),
  <Skeleton height={176} radius="md" />,
);
