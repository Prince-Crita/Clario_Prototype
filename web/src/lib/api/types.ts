/** What the app knows about the signed-in user and their workspaces. Built from GET /api/me. */

export type Role = "owner" | "admin" | "member" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
}

/** The only Zoho facts the workspace pages need (never the OAuth settings). */
export interface ZohoSummary {
  is_connected: boolean;
  organization_name: string;
  currency_code: string;
}

export interface WorkspaceSummary {
  id: string;
  slug: string;
  name: string;
  /** "active" for every workspace /api/me returns today. */
  status: string;
  role: Role;
  zoho: ZohoSummary;
}

export interface Session {
  user: User;
  workspaces: WorkspaceSummary[];
}
