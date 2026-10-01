/**
 * Code-split a component without the half-second React adds to `React.lazy`.
 *
 * Whenever a Suspense fallback is shown, React keeps it up for at least 300 ms before it reveals
 * the content that replaced it, even when that content is already in the cache. Entering the
 * dashboard hit that on every visit: its chunk was loaded long before the skeleton went away.
 * This loader uses no Suspense: the component renders in the same commit as soon as its module is
 * loaded, and `fallback` shows only while it is not.
 *
 *   const Chart = lazyComponent(() => import("./Chart"), <Skeleton />);
 *   Chart.preload();   // start the download now (idle time, hover) so the first render is instant
 *
 * A failed download is thrown to the nearest error boundary, as `React.lazy` does, and the next
 * `preload()` or mount tries again.
 */
import { useEffect, useState, type ComponentType, type ReactNode } from "react";

type Loader<P> = () => Promise<{ default: ComponentType<P> }>;

export function lazyComponent<P extends object>(load: Loader<P>, fallback: ReactNode = null) {
  let loaded: ComponentType<P> | null = null;
  let pending: Promise<void> | null = null;

  const preload = (): Promise<void> => {
    pending ??= load().then(
      (module) => {
        loaded = module.default;
      },
      (error: unknown) => {
        pending = null; // allow a retry
        throw error;
      },
    );
    return pending;
  };

  function Lazy(props: P) {
    const [Component, setComponent] = useState<ComponentType<P> | null>(() => loaded);
    const [error, setError] = useState<unknown>(null);
    useEffect(() => {
      if (Component) return;
      let alive = true;
      preload().then(
        () => {
          if (alive && loaded) setComponent(() => loaded);
        },
        (reason: unknown) => {
          if (alive) setError(reason ?? new Error("Failed to load a part of the page"));
        },
      );
      return () => {
        alive = false;
      };
    }, [Component]);
    if (error) throw error;
    return Component ? <Component {...props} /> : <>{fallback}</>;
  }

  return Object.assign(Lazy, { preload });
}
