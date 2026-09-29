/**
 * /w/:workspace/:integration — where a system's card leads (plan §9.3): its domain dashboard once
 * it is connected to an account, otherwise the connection page. A callback or setup notice in the
 * query string (?error, ?connected, ?reconnected) is shown on the connection page first.
 */
import { Navigate, useParams, useSearchParams } from "react-router";

import { useCurrentWorkspace } from "../workspace/hooks";
import { DASHBOARDS } from "./dashboards";
import { useIntegration } from "./hooks";
import { IntegrationPage } from "./IntegrationPage";

const NOTICES = ["error", "connected", "reconnected"];

export function IntegrationIndex() {
  const { integration: key = "" } = useParams();
  const [params] = useSearchParams();
  const workspace = useCurrentWorkspace();
  const tile = useIntegration(workspace.id, key).data;
  const dashboard = tile ? DASHBOARDS[tile.domain] : undefined;
  const linked = Boolean(tile?.connection?.account) && tile?.connection_state !== "pending";
  if (dashboard && linked && !NOTICES.some((n) => params.has(n))) {
    return <Navigate to={`/w/${workspace.slug}/${key}/${dashboard}`} replace />;
  }
  return <IntegrationPage />;
}
