/** Friendly aliases over the generated contract (`npm run gen:api` regenerates schema.d.ts). */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Session = Schemas["SessionOut"];
export type User = Schemas["UserOut"];
export type WorkspaceSummary = Schemas["WorkspaceSummary"];
export type WorkspaceDetail = Schemas["WorkspaceDetail"];
export type Member = Schemas["Member"];
export type Role = Schemas["Role"];
export type Permission = Schemas["Permission"];
export type IntegrationTile = Schemas["IntegrationTile"];
export type ConnectionState = IntegrationTile["connection_state"];
export type Connection = Schemas["ConnectionOut"];
export type ExternalAccount = Schemas["ExternalAccountOut"];
export type SyncStatus = Schemas["SyncStatus"];
export type DatasetStatus = Schemas["DatasetStatusOut"];
export type FinanceOverview = Schemas["Overview"];
export type FinanceTrends = Schemas["Trends"];
export type FinanceReceivables = Schemas["Receivables"];
export type FinanceGst = Schemas["GstOut"];
export type FinanceBalanceSheet = Schemas["BalanceSheet"];
export type FinanceMeta = Schemas["Meta"];
export type Kpi = Schemas["Kpi"];
export type ActionItem = Schemas["ActionItemOut"];
export type MonthFigures = Schemas["MonthFigures"];
export type CashBucket = Schemas["CashBucketOut"];
export type Invoice = Schemas["InvoiceOut"];
export type InvoicePage = Schemas["InvoicePage"];
export type ClientBilled = Schemas["ClientBilled"];
export type AssistantInfo = Schemas["AssistantInfo"];
export type ConversationSummary = Schemas["ConversationSummary"];
export type ConversationDetail = Schemas["ConversationDetail"];
export type ChatMessage = Schemas["MessageOut"];
export type ChatReply = Schemas["Reply"];
export type AssistantStatus = Schemas["AssistantStatus"];
