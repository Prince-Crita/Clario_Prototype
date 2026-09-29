/** The Command Centre (and its charts) loads on first visit, not with the app shell (plan §30). */
import { lazy, Suspense } from "react";

import { Skeleton } from "../design-system";

const CommandCentre = lazy(() => import("../features/finance/CommandCentre"));

export function LazyCommandCentre() {
  return (
    <Suspense fallback={<Skeleton height={176} radius="md" />}>
      <CommandCentre />
    </Suspense>
  );
}
