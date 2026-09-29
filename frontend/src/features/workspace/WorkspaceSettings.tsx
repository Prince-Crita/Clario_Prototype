import { useSearchParams } from "react-router";

import { Alert, DataTable, PageHeader, Skeleton, Tabs, type Column } from "../../design-system";
import type { Member } from "../../lib/api/types";
import { ROLE_LABEL } from "../../lib/labels";
import { ChangePasswordForm } from "../auth/ChangePasswordForm";
import { useRequiredSession } from "../auth/hooks";
import { useCurrentWorkspace, useMembers } from "./hooks";
import styles from "./WorkspaceSettings.module.css";

const MEMBER_COLUMNS: Column<Member>[] = [
  { key: "name", header: "Name", cell: (m) => m.full_name || "—" },
  { key: "email", header: "Email", cell: (m) => m.email },
  { key: "role", header: "Role", cell: (m) => ROLE_LABEL[m.role] },
];

function MembersPanel() {
  const workspace = useCurrentWorkspace();
  const members = useMembers(workspace.id);
  if (members.isPending) return <Skeleton height={160} radius="md" />;
  if (members.isError)
    return (
      <Alert tone="negative">Members couldn't be loaded. Refresh the page to try again.</Alert>
    );
  return (
    <div className={styles.panel}>
      <p className={styles.lead}>
        People with access to {workspace.name}. To add or remove people, contact your Crita
        administrator.
      </p>
      <DataTable
        caption={`Members of ${workspace.name}`}
        hideCaption
        columns={MEMBER_COLUMNS}
        rows={members.data}
        rowKey={(m) => m.user_id}
      />
    </div>
  );
}

function AccountPanel() {
  const { user } = useRequiredSession();
  return (
    <div className={styles.panel}>
      <dl className={styles.facts}>
        <div>
          <dt>Name</dt>
          <dd>{user.full_name || "—"}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{user.email}</dd>
        </div>
      </dl>
      <section className={styles.formSection} aria-labelledby="password-title">
        <h2 id="password-title" className={styles.formTitle}>
          Change password
        </h2>
        <ChangePasswordForm />
      </section>
    </div>
  );
}

export function WorkspaceSettings() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "account" ? "account" : "members";
  return (
    <>
      <PageHeader title="Settings" divider={false} />
      <Tabs
        label="Settings sections"
        value={tab}
        onValueChange={(value) =>
          setParams(value === "members" ? {} : { tab: value }, { replace: true })
        }
        tabs={[
          { value: "members", label: "Members", content: <MembersPanel /> },
          { value: "account", label: "Your account", content: <AccountPanel /> },
        ]}
      />
    </>
  );
}
