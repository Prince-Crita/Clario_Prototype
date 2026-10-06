import { Status } from "../../design-system/primitives/Status";
import styles from "./IntegrationTile.module.css";

interface IntegrationTileProps {
  domain: string;
  vendor: string;
  name: string;
  summary: string;
  status: { label: string; tone: "neutral" | "positive" };
  /** The connected account (e.g. the Zoho organisation name). */
  account?: string | undefined;
}

/** A system card. Display only for now: nothing to click until its page exists. */
export function IntegrationTile({
  domain,
  vendor,
  name,
  summary,
  status,
  account,
}: IntegrationTileProps) {
  return (
    <article className={styles.tile}>
      <p className={styles.domain}>
        {domain}
        <span aria-hidden="true"> · </span>
        {vendor}
      </p>
      <h3 className={styles.name}>{name}</h3>
      <p className={styles.summary}>{summary}</p>
      <div className={styles.footer}>
        <span className={styles.state}>
          <Status tone={status.tone}>{status.label}</Status>
          {account ? <span className={styles.account}>{account}</span> : null}
        </span>
      </div>
    </article>
  );
}
