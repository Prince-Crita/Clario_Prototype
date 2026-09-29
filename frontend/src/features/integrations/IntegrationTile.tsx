/**
 * Integration card — the ONLY card pattern in Clario (plan §27.3).
 * Available: the whole card is one link (stretched heading link) to the integration page.
 * Coming soon: muted, labelled, and not a link — nothing to click, focus or hover.
 */
import { ArrowRight } from "lucide-react";
import { Link } from "react-router";

import { Status } from "../../design-system";
import type { IntegrationTile as Tile } from "../../lib/api/types";
import { STATE_STATUS } from "./connection";
import styles from "./IntegrationTile.module.css";

interface IntegrationTileProps {
  tile: Tile;
  href: string;
}

/** What a manager is invited to do next, by connection state. */
const CTA: Partial<Record<Tile["connection_state"], string>> = {
  not_connected: "Set up",
  pending: "Finish setup",
  needs_reauth: "Reconnect",
  error: "Reconnect",
};

export function IntegrationTile({ tile, href }: IntegrationTileProps) {
  const comingSoon = tile.availability === "coming_soon";
  const status = STATE_STATUS[tile.connection_state];
  const account = tile.connection?.account?.name;
  const cta = CTA[tile.connection_state];
  return (
    <article className={styles.tile} data-coming-soon={comingSoon || undefined}>
      <p className={styles.domain}>
        {tile.domain_name}
        <span aria-hidden="true"> · </span>
        {tile.vendor}
      </p>
      <h3 className={styles.name}>
        {comingSoon ? (
          tile.name
        ) : (
          <Link to={href} className={styles.link}>
            {tile.name}
          </Link>
        )}
      </h3>
      <p className={styles.summary}>{tile.summary}</p>
      <div className={styles.footer}>
        {comingSoon ? (
          <span className={styles.comingSoon}>Coming soon</span>
        ) : (
          <>
            <span className={styles.state}>
              <Status tone={status.tone}>{status.label}</Status>
              {account ? <span className={styles.account}>{account}</span> : null}
            </span>
            {cta && tile.can_manage ? (
              <span className={styles.cta} aria-hidden="true">
                {cta} <ArrowRight size={14} />
              </span>
            ) : null}
          </>
        )}
      </div>
    </article>
  );
}
