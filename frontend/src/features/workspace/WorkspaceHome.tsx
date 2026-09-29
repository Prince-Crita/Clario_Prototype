/**
 * Workspace home (plan §27.4): header + the integration catalog for this workspace.
 */
import { Alert, EmptyState, PageHeader, Skeleton } from "../../design-system";
import { IntegrationTile } from "../integrations/IntegrationTile";
import { useIntegrations } from "../integrations/hooks";
import { fiscalYearLabel, ROLE_LABEL, timeZoneLabel } from "../../lib/labels";
import { useCurrentWorkspace, useWorkspaceDetail } from "./hooks";
import styles from "./WorkspaceHome.module.css";

export function WorkspaceHome() {
  const workspace = useCurrentWorkspace();
  const detail = useWorkspaceDetail(workspace.id);
  const integrations = useIntegrations(workspace.id);

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title={workspace.name}
        meta={
          detail.data ? (
            <>
              <span>Your role: {ROLE_LABEL[workspace.role]}</span>
              <span>Financial year {fiscalYearLabel(detail.data.fiscal_year_start_month)}</span>
              <span>Currency {detail.data.base_currency}</span>
              <span>{timeZoneLabel(detail.data.timezone)}</span>
            </>
          ) : (
            <Skeleton width={320} height={16} />
          )
        }
      />
      <section className={styles.section} aria-labelledby="systems-title">
        <div className={styles.sectionHeader}>
          <h2 id="systems-title" className={styles.sectionTitle}>
            Connected systems
          </h2>
          <p className={styles.sectionLead}>
            The business systems Clario reads for this workspace. Each one has its own dashboard and
            assistant.
          </p>
        </div>
        {integrations.isPending ? (
          <div className={styles.grid} aria-busy="true">
            <Skeleton height={188} radius="md" />
            <Skeleton height={188} radius="md" />
          </div>
        ) : integrations.isError ? (
          <Alert tone="negative">Systems couldn't be loaded. Refresh the page to try again.</Alert>
        ) : integrations.data.length === 0 ? (
          <EmptyState title="No systems are available to this workspace yet.">
            Crita enables systems for each workspace. Contact your Crita administrator to add one.
          </EmptyState>
        ) : (
          <ul className={styles.grid}>
            {integrations.data.map((tile) => (
              <li key={tile.key}>
                <IntegrationTile tile={tile} href={`/w/${workspace.slug}/${tile.key}`} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
