/**
 * /w/:workspace/:integration/setup — the last setup step after consent: choose the account
 * (a Zoho Books organisation) Clario reads. The OAuth callback lands here after a first approval.
 * Anyone arriving without an approved, unfinished connection is sent to the integration page.
 */
import { Check } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router";

import { Alert, Button, EmptyState, PageHeader, Skeleton } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import type { ExternalAccount, IntegrationTile } from "../../lib/api/types";
import { useCurrentWorkspace } from "../workspace/hooks";
import { useAccounts, useConnectIntegration, useIntegration, useSelectAccount } from "./hooks";
import styles from "./SetupPage.module.css";

export function SetupPage() {
  const { integration: key = "" } = useParams();
  const workspace = useCurrentWorkspace();
  const integration = useIntegration(workspace.id, key);
  // Owned here, not in ChooseAccount: once it succeeds the refetched tile says "connected", and
  // this page must leave with the success notice rather than through the guard below.
  const select = useSelectAccount(workspace.id, integration.data?.connection?.id ?? "");
  const overview = `/w/${workspace.slug}/${key}`;

  if (select.isSuccess) return <Navigate to={`${overview}?connected=1`} replace />;

  if (integration.isPending) {
    return (
      <div className={styles.page} aria-busy="true">
        <Skeleton width="40%" height={28} />
        <Skeleton height={220} radius="md" />
      </div>
    );
  }
  const tile = integration.data;
  const connection = tile?.connection;
  if (!tile || !tile.can_manage || tile.connection_state !== "pending" || !connection?.authorised) {
    return <Navigate to={overview} replace />;
  }
  return (
    <ChooseAccount
      tile={tile}
      connectionId={connection.id}
      workspaceId={workspace.id}
      overview={overview}
      select={select}
    />
  );
}

interface ChooseAccountProps {
  tile: IntegrationTile;
  connectionId: string;
  workspaceId: string;
  overview: string;
  select: ReturnType<typeof useSelectAccount>;
}

function ChooseAccount({ tile, connectionId, workspaceId, overview, select }: ChooseAccountProps) {
  const accounts = useAccounts(workspaceId, connectionId);
  const restart = useConnectIntegration(workspaceId, tile.key);
  const [picked, setPicked] = useState<string | null>(null);
  const noun = tile.account_noun;

  const options = accounts.data ?? [];
  const suggested =
    options.find((a) => a.selectable && a.is_default) ?? options.find((a) => a.selectable);
  const chosenId = picked ?? suggested?.id ?? null;
  const chosen = options.find((a) => a.id === chosenId);
  const failure =
    (select.error instanceof ApiError && select.error.detail) ||
    (accounts.error instanceof ApiError && accounts.error.detail) ||
    null;
  const startAgain = (
    <Button
      variant="ghost"
      pending={restart.isPending || restart.isSuccess}
      pendingLabel="Opening…"
      onClick={() => restart.mutate(tile.connection?.region ?? undefined)}
    >
      Start again
    </Button>
  );

  return (
    <div className={styles.page}>
      <PageHeader eyebrow={`Set up ${tile.name}`} title={`Choose your ${noun}`} />
      <ol className={styles.steps} aria-label="Setup steps">
        <li data-state="done">
          <Check size={14} aria-hidden="true" /> Approve read-only access
        </li>
        <li data-state="current" aria-current="step">
          Choose {noun}
        </li>
        <li data-state="next">Start using Clario</li>
      </ol>

      {failure ? (
        <Alert tone="warning" action={startAgain}>
          {failure}
        </Alert>
      ) : null}

      {accounts.isPending ? (
        <Skeleton height={160} radius="md" />
      ) : accounts.isError ? null : options.length === 0 ? (
        <EmptyState
          title={`This ${tile.vendor} login has no ${tile.name} ${noun}s`}
          action={startAgain}
        >
          Sign in with the {tile.vendor} login your business uses for {tile.name}.
        </EmptyState>
      ) : (
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault();
            if (!chosenId) return;
            select.mutate(chosenId);
          }}
        >
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>
              Which {tile.name} {noun} should Clario read?
            </legend>
            <p className={styles.hint}>
              Clario reads one {noun} per workspace. To use a different one later, disconnect and
              connect again.
            </p>
            <div className={styles.options}>
              {options.map((account) => (
                <AccountOption
                  key={account.id}
                  account={account}
                  noun={noun}
                  checked={account.id === chosenId}
                  onChange={() => setPicked(account.id)}
                />
              ))}
            </div>
          </fieldset>
          <div className={styles.actions}>
            <Button
              type="submit"
              variant="primary"
              disabled={!chosen}
              pending={select.isPending}
              pendingLabel="Connecting…"
            >
              {chosen ? `Use ${chosen.name}` : `Choose an ${noun}`}
            </Button>
            <Link to={overview} className={styles.cancel}>
              Not now
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

interface AccountOptionProps {
  account: ExternalAccount;
  noun: string;
  checked: boolean;
  onChange: () => void;
}

function AccountOption({ account, noun, checked, onChange }: AccountOptionProps) {
  const detail = [account.detail, `ID ${account.id}`].filter(Boolean).join(" · ");
  return (
    <label
      className={styles.option}
      data-checked={checked || undefined}
      data-disabled={!account.selectable || undefined}
    >
      <input
        type="radio"
        name="account"
        value={account.id}
        checked={checked}
        disabled={!account.selectable}
        onChange={onChange}
        className={styles.radio}
      />
      <span className={styles.optionText}>
        <span className={styles.optionName}>
          {account.name}
          {account.is_default ? <span className={styles.badge}>Default {noun}</span> : null}
        </span>
        <span className={styles.optionDetail}>
          {account.selectable ? detail : `Not supported by the ${noun}'s plan · ${detail}`}
        </span>
      </span>
    </label>
  );
}
