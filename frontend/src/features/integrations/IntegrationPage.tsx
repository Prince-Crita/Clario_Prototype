/**
 * /w/:workspace/:integration — one integration, by connection state (plan §9.3, §17):
 *   not connected  → what Clario reads, the read-only promise, where the account lives, Connect
 *   pending        → continue to choosing the account (or start again)
 *   connected      → connection details; Reconnect and Disconnect for owners/admins
 *   needs_reauth   → the same, with a warning and Reconnect first
 * The OAuth callback lands here with `?error=<code>` or `?reconnected=1`; the setup page with
 * `?connected=1`. Coming-soon or unknown integrations explain instead of rendering a dead end.
 */
import { Check } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import {
  Alert,
  Button,
  EmptyState,
  PageHeader,
  SelectField,
  Skeleton,
  Status,
} from "../../design-system";
import { ApiError } from "../../lib/api/client";
import type { Connection, IntegrationTile } from "../../lib/api/types";
import { fiscalYearLabel, timeZoneLabel } from "../../lib/labels";
import { useCurrentWorkspace } from "../workspace/hooks";
import { DASHBOARDS } from "./dashboards";
import { DataPanel } from "./DataPanel";
import { STATE_STATUS, connectFailureMessage } from "./connection";
import { useConnectIntegration, useDisconnect, useIntegration } from "./hooks";
import styles from "./IntegrationPage.module.css";

export function IntegrationPage() {
  const { integration: key = "" } = useParams();
  const [params] = useSearchParams();
  const workspace = useCurrentWorkspace();
  const integration = useIntegration(workspace.id, key);
  const home = `/w/${workspace.slug}`;

  if (integration.isPending) {
    return (
      <div className={styles.loading} aria-busy="true">
        <Skeleton width="30%" height={28} />
        <Skeleton height={180} radius="md" />
      </div>
    );
  }

  if (integration.isError || integration.data.availability === "coming_soon") {
    const notFound = integration.error instanceof ApiError && integration.error.status === 404;
    const title = integration.data
      ? `${integration.data.name} isn't available yet`
      : notFound
        ? "This system isn't available to your workspace"
        : "This system couldn't be loaded";
    return (
      <EmptyState title={title} action={<Link to={home}>Back to {workspace.name}</Link>}>
        {integration.data
          ? "Crita will let you know when it can be connected."
          : "Check the address, or go back to your workspace to see the systems you can use."}
      </EmptyState>
    );
  }

  const tile = integration.data;
  const status = STATE_STATUS[tile.connection_state];
  const connection = tile.connection;
  const linked = connection?.account && tile.connection_state !== "pending" ? connection : null;
  const failure = params.get("error");
  const accountName = connection?.account?.name ?? `your ${tile.account_noun}`;

  return (
    <>
      <PageHeader
        eyebrow={`${tile.domain_name} · ${tile.vendor}`}
        title={tile.name}
        meta={<Status tone={status.tone}>{status.label}</Status>}
        actions={
          linked && DASHBOARDS[tile.domain] ? (
            <Link
              to={`/w/${workspace.slug}/${tile.key}/${DASHBOARDS[tile.domain] ?? ""}`}
              className={styles.primaryLink}
            >
              Open {tile.domain_name} Command Centre
            </Link>
          ) : null
        }
      />
      {failure ? (
        <Alert tone="warning" title="Nothing was changed">
          {connectFailureMessage(failure, tile)}
        </Alert>
      ) : params.has("reconnected") && tile.connection_state === "connected" ? (
        <Alert tone="positive">Reconnected. Clario can read {accountName} again.</Alert>
      ) : params.has("connected") && tile.connection_state === "connected" ? (
        <Alert tone="positive">
          {tile.name} is connected to {accountName}.
        </Alert>
      ) : null}
      {tile.connection_state === "needs_reauth" && !failure ? (
        <Alert tone="warning" title={`Reconnect ${tile.name}`}>
          {tile.vendor} stopped accepting Clario's access to {accountName}, so Clario can't read new
          data.{" "}
          {tile.can_manage
            ? "Reconnect to sign in again — nothing is lost."
            : "Ask a workspace owner or admin to reconnect it."}
        </Alert>
      ) : null}
      {linked ? (
        <ConnectedView tile={tile} connection={linked} workspaceId={workspace.id} />
      ) : (
        <SetupView tile={tile} workspaceId={workspace.id} workspaceName={workspace.name} />
      )}
    </>
  );
}

// ---------------------------------------------------------------- not connected / pending

interface SetupViewProps {
  tile: IntegrationTile;
  workspaceId: string;
  workspaceName: string;
}

function SetupView({ tile, workspaceId, workspaceName }: SetupViewProps) {
  const awaitingAccount = tile.connection_state === "pending" && tile.connection?.authorised;
  return (
    <div className={styles.layout}>
      <section className={styles.panel} aria-labelledby="reads-title">
        <h2 id="reads-title" className={styles.panelTitle}>
          What Clario reads
        </h2>
        <ul className={styles.reads}>
          {tile.reads.map((item) => (
            <li key={item}>
              <Check size={16} aria-hidden="true" className={styles.tick} />
              {item}
            </li>
          ))}
        </ul>
        {tile.read_only ? (
          <p className={styles.promise}>
            Clario only reads from {tile.name}. It can never create, change or delete anything in
            your books.
          </p>
        ) : null}
      </section>

      {!tile.can_manage ? (
        <section className={styles.panel} aria-labelledby="connect-title">
          <h2 id="connect-title" className={styles.panelTitle}>
            Connect {tile.name}
          </h2>
          <p className={styles.text}>
            Only workspace owners and admins can connect {tile.name}. Ask one of them to set it up
            for {workspaceName}.
          </p>
        </section>
      ) : awaitingAccount ? (
        <ChooseAccountPanel tile={tile} workspaceId={workspaceId} />
      ) : (
        <ConnectPanel tile={tile} workspaceId={workspaceId} />
      )}
    </div>
  );
}

function ConnectPanel({ tile, workspaceId }: { tile: IntegrationTile; workspaceId: string }) {
  const connect = useConnectIntegration(workspaceId, tile.key);
  const [region, setRegion] = useState(tile.connection?.region ?? tile.regions[0]?.code ?? "");
  const connectError = connect.error instanceof ApiError ? connect.error.detail : null;

  return (
    <section className={styles.panel} aria-labelledby="connect-title">
      <h2 id="connect-title" className={styles.panelTitle}>
        Connect {tile.name}
      </h2>
      <p className={styles.text}>
        You'll sign in to {tile.vendor} and approve read-only access. Clario never sees your{" "}
        {tile.vendor} password.
      </p>
      {tile.regions.length > 1 ? (
        <SelectField
          label={`Where is your ${tile.vendor} account?`}
          hint={`The ${tile.vendor} site you sign in to. If you're not sure, keep the first one.`}
          options={tile.regions.map((r) => ({ value: r.code, label: r.label }))}
          value={region}
          onChange={(event) => setRegion(event.target.value)}
        />
      ) : null}
      {connectError ? <Alert tone="warning">{connectError}</Alert> : null}
      <div>
        <Button
          variant="primary"
          pending={connect.isPending || connect.isSuccess}
          pendingLabel={`Opening ${tile.vendor}…`}
          onClick={() => connect.mutate(region || undefined)}
        >
          Connect {tile.name}
        </Button>
      </div>
    </section>
  );
}

function ChooseAccountPanel({ tile, workspaceId }: { tile: IntegrationTile; workspaceId: string }) {
  const navigate = useNavigate();
  const connect = useConnectIntegration(workspaceId, tile.key);
  return (
    <section className={styles.panel} aria-labelledby="connect-title">
      <h2 id="connect-title" className={styles.panelTitle}>
        Choose your {tile.account_noun}
      </h2>
      <p className={styles.text}>
        Access to {tile.vendor} is approved. Choose which {tile.name} {tile.account_noun} Clario
        should read to finish setting up.
      </p>
      <div className={styles.actions}>
        <Button variant="primary" onClick={() => void navigate("setup")}>
          Choose {tile.account_noun}
        </Button>
        <Button
          variant="ghost"
          pending={connect.isPending || connect.isSuccess}
          pendingLabel="Opening…"
          onClick={() => connect.mutate(tile.connection?.region ?? undefined)}
        >
          Start again
        </Button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- connected

interface ConnectedViewProps {
  tile: IntegrationTile;
  connection: Connection;
  workspaceId: string;
}

const DATE = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

function ConnectedView({ tile, connection, workspaceId }: ConnectedViewProps) {
  const account = connection.account;
  const noun = tile.account_noun.charAt(0).toUpperCase() + tile.account_noun.slice(1);
  const region = tile.regions.find((r) => r.code === connection.region)?.label;
  const rows: [string, string][] = [
    [noun, account?.name ?? "—"],
    [`${noun} ID`, account?.id ?? "—"],
  ];
  if (account?.currency) rows.push(["Currency", account.currency]);
  if (account?.fiscal_year_start_month)
    rows.push(["Financial year", fiscalYearLabel(account.fiscal_year_start_month)]);
  if (account?.timezone) rows.push(["Time zone", timeZoneLabel(account.timezone)]);
  if (region) rows.push(["Data center", region]);
  if (connection.connected_at)
    rows.push([
      "Connected",
      `${DATE.format(new Date(connection.connected_at))}${connection.connected_by ? ` by ${connection.connected_by}` : ""}`,
    ]);

  return (
    <div className={styles.layout}>
      <section className={styles.panel} aria-labelledby="details-title">
        <h2 id="details-title" className={styles.panelTitle}>
          Connection
        </h2>
        <dl className={styles.details}>
          {rows.map(([term, value]) => (
            <div key={term} className={styles.detail}>
              <dt>{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {tile.read_only ? (
          <p className={styles.promise}>
            Read-only: Clario can never create, change or delete anything in {tile.name}.
          </p>
        ) : null}
      </section>
      <ManagePanel tile={tile} connection={connection} workspaceId={workspaceId} />
      <DataPanel tile={tile} workspaceId={workspaceId} connectionId={connection.id} />
    </div>
  );
}

function ManagePanel({ tile, connection, workspaceId }: ConnectedViewProps) {
  const connect = useConnectIntegration(workspaceId, tile.key);
  const disconnect = useDisconnect(workspaceId, connection.id);
  const [confirming, setConfirming] = useState(false);
  const accountName = connection.account?.name ?? `this ${tile.account_noun}`;
  const needsReauth = tile.connection_state !== "connected";
  const failure =
    (connect.error instanceof ApiError && connect.error.detail) ||
    (disconnect.error instanceof ApiError && disconnect.error.detail) ||
    null;

  if (!tile.can_manage) {
    return (
      <section className={styles.panel} aria-labelledby="manage-title">
        <h2 id="manage-title" className={styles.panelTitle}>
          Manage
        </h2>
        <p className={styles.text}>
          Only workspace owners and admins can reconnect or disconnect {tile.name}.
        </p>
      </section>
    );
  }

  return (
    <section className={styles.panel} aria-labelledby="manage-title">
      <h2 id="manage-title" className={styles.panelTitle}>
        Manage
      </h2>
      <p className={styles.text}>
        {needsReauth
          ? `Sign in to ${tile.vendor} again to restore Clario's access to ${accountName}.`
          : `Reconnect when ${tile.vendor} asks you to sign in again. Clario keeps reading ${accountName}.`}
      </p>
      {failure ? <Alert tone="warning">{failure}</Alert> : null}
      <div className={styles.actions}>
        <Button
          variant={needsReauth ? "primary" : "secondary"}
          pending={connect.isPending || connect.isSuccess}
          pendingLabel={`Opening ${tile.vendor}…`}
          onClick={() => connect.mutate(connection.region ?? undefined)}
        >
          Reconnect
        </Button>
        {confirming ? null : (
          <Button variant="ghost" onClick={() => setConfirming(true)}>
            Disconnect…
          </Button>
        )}
      </div>
      {confirming ? (
        <div className={styles.confirm} role="group" aria-labelledby="disconnect-title">
          <p id="disconnect-title" className={styles.confirmTitle}>
            Disconnect {tile.name}?
          </p>
          <p className={styles.text}>
            Clario stops reading {accountName} and deletes its stored access. Nothing in{" "}
            {tile.vendor} changes, and you can connect again at any time.
          </p>
          <div className={styles.actions}>
            <Button
              variant="danger"
              pending={disconnect.isPending}
              pendingLabel="Disconnecting…"
              onClick={() => disconnect.mutate()}
            >
              Disconnect
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
