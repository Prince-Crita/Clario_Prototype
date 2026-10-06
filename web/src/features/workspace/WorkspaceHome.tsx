import { PageHeader } from "../../design-system/primitives/PageHeader";
import { ROLE_LABEL } from "../../lib/labels";
import { useCurrentWorkspace } from "./hooks";
import { IntegrationTile } from "./IntegrationTile";
import styles from "./WorkspaceHome.module.css";

export function WorkspaceHome() {
  const workspace = useCurrentWorkspace();
  const { zoho } = workspace;

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title={workspace.name}
        meta={
          <>
            <span>Your role: {ROLE_LABEL[workspace.role]}</span>
            {zoho.currency_code ? <span>Currency {zoho.currency_code}</span> : null}
          </>
        }
      />
      <section className={styles.section} aria-labelledby="systems-title">
        <div className={styles.sectionHeader}>
          <h2 id="systems-title" className={styles.sectionTitle}>
            Connected systems
          </h2>
          <p className={styles.sectionLead}>The business system Clario reads for this workspace.</p>
        </div>
        <ul className={styles.grid}>
          <li>
            <IntegrationTile
              domain="Accounting"
              vendor="Zoho Books"
              name="Zoho Books"
              summary="Clario reads this workspace's Zoho Books data for analytics and chat."
              status={
                zoho.is_connected
                  ? { label: "Connected", tone: "positive" }
                  : { label: "Not connected", tone: "neutral" }
              }
              account={zoho.is_connected ? zoho.organization_name : undefined}
            />
          </li>
        </ul>
      </section>
    </>
  );
}
