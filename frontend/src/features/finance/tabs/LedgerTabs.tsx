/**
 * GST and Balance Sheet (plan §22.2, §27.10). Both await the director's definitions (Q5, Q6): they
 * show the ledger figures Clario reads and say so plainly.
 *   GST          one panel: the answer in words over the equation (output − input = net, the net
 *                in Crita green); GST without GST accounts is an informative state, not an error.
 *   Balance sheet the answer beside the summary, then one statement document: what you own and
 *                what you owe side by side, each group with its lines and the server's group
 *                total (never a total of Clario's own).
 */
import { Receipt } from "lucide-react";

import { BasisTag, Figure } from "../../../design-system";
import type { FinanceBalanceSheet, FinanceGst } from "../../../lib/api/types";
import { AskLink, Section } from "../components/Section";
import { dateLabel, isNegative, money } from "../format";
import { useFinanceTab } from "../hooks";
import { TabBody, type TabProps } from "./TabBody";
import styles from "./tabs.module.css";

export function GstTab({ workspaceId, connectionId, ask }: TabProps) {
  const query = useFinanceTab<FinanceGst>(workspaceId, connectionId, "gst");
  return (
    <TabBody query={query}>
      {(g) => {
        const asOf = g.as_of ? `as of ${dateLabel(g.as_of)}` : undefined;
        if (g.net_payable === null) {
          return (
            <div className={styles.stateCard}>
              <span className={styles.stateIcon} aria-hidden="true">
                <Receipt size={20} />
              </span>
              <div>
                <h2 className={styles.stateTitle}>GST isn't set up for this organisation</h2>
                <p className={styles.muted}>
                  No GST accounts were found in the connected books. If the organisation is
                  registered for GST, check that GST is switched on in Zoho Books; this page fills
                  in on the next sync.
                </p>
                <p className={styles.note}>
                  When GST is available: tax collected on sales, input credit on purchases, the net
                  position and, once the period is agreed, filing-period summaries.
                </p>
              </div>
            </div>
          );
        }
        const credit = isNegative(g.net_payable);
        const net = money(g.net_payable.replace(/^-/, ""));
        return (
          <div className={styles.stack}>
            <div className={styles.answer}>
              <p className={styles.kicker}>Tax position</p>
              <p className={styles.answerLine}>
                {credit ? (
                  <>
                    More GST was paid than collected: <strong>{net}</strong> of credit carries
                    forward.
                  </>
                ) : (
                  <>
                    <strong>{net}</strong> of GST is payable with the next return, {asOf}.
                  </>
                )}
              </p>

              <section className={styles.equation} aria-label="GST summary">
                <div className={styles.term}>
                  <span className={styles.termLabel}>Output GST</span>
                  <span className={styles.termValue}>{money(g.output_tax ?? "0")}</span>
                  <span className={styles.termNote}>Collected on sales</span>
                </div>
                <span className={styles.operator} aria-hidden="true">
                  −
                </span>
                <div className={styles.term}>
                  <span className={styles.termLabel}>Input credit</span>
                  <span className={styles.termValue}>{money(g.input_tax ?? "0")}</span>
                  <span className={styles.termNote}>Paid on purchases</span>
                </div>
                <span className={styles.operator} aria-hidden="true">
                  =
                </span>
                <div className={styles.term} data-result>
                  <span className={styles.termLabel}>
                    {credit ? "Credit carried forward" : "Net GST payable"}
                  </span>
                  <span className={styles.termValue}>{net}</span>
                  <span className={styles.termNote}>
                    {credit ? "More paid than collected" : "Owed with the next return"}
                  </span>
                </div>
              </section>
            </div>

            <Section
              eyebrow="From the ledger"
              title="GST position"
              description="Output tax less input credit."
              aside={<AskLink ask={ask} question="What is our GST position?" />}
            >
              <div className={styles.split}>
                <section className={styles.panel} aria-label="GST statement">
                  <header className={styles.panelHeader}>
                    <h3 className={styles.panelTitle}>Statement</h3>
                    <BasisTag basis="ledger" window={asOf} />
                  </header>
                  <dl className={styles.statement}>
                    <div>
                      <dt>Output GST (collected on sales)</dt>
                      <dd>{money(g.output_tax ?? "0")}</dd>
                    </div>
                    <div>
                      <dt>Less input credit (paid on purchases)</dt>
                      <dd>− {money(g.input_tax ?? "0")}</dd>
                    </div>
                    <div className={styles.total}>
                      <dt>{credit ? "Credit carried forward" : "Payable to government"}</dt>
                      <dd>{net}</dd>
                    </div>
                  </dl>
                </section>
                <div className={styles.pending}>
                  <h3>Early view</h3>
                  <p className={styles.muted}>
                    The GST period and method are still being agreed. Until then this shows the
                    ledger position as of the latest balance sheet. Check it against your GST return
                    before filing.
                  </p>
                  <ul>
                    <li>Filing-period summaries (GSTR-1 and GSTR-3B views)</li>
                    <li>Tax collected and paid, month by month</li>
                    <li>Due dates for the next return</li>
                  </ul>
                </div>
              </div>
            </Section>
          </div>
        );
      }}
    </TabBody>
  );
}

// ---------------------------------------------------------------- balance sheet

const OWE = /liabilit|payable|creditor|loan|borrow|credit card|duties|provision|overdraft/i;
const EQUITY = /equity|capital|reserve|retained|surplus|owner|drawings/i;

type Group = FinanceBalanceSheet["groups"][number];

function Statement({ groups }: { groups: Group[] }) {
  return (
    <>
      {groups.map((group) => (
        <table key={group.name} className={styles.ledger}>
          <caption className="visually-hidden">{group.name}</caption>
          <thead>
            <tr className={styles.ledgerHead}>
              <th scope="col">{group.name}</th>
              <th scope="col">
                <span className="visually-hidden">Balance</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {group.lines.map((line) => (
              <tr key={line.name}>
                <th scope="row">{line.name}</th>
                <td className={isNegative(line.balance) ? styles.negative : undefined}>
                  {money(line.balance)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className={styles.ledgerFoot}>
              <th scope="row">Total {group.name.toLowerCase()}</th>
              <td>{money(group.total)}</td>
            </tr>
          </tfoot>
        </table>
      ))}
    </>
  );
}

export function BalanceSheetTab({ workspaceId, connectionId, ask }: TabProps) {
  const query = useFinanceTab<FinanceBalanceSheet>(workspaceId, connectionId, "balance-sheet");
  return (
    <TabBody query={query}>
      {(b) => {
        const asOf = b.as_of ? `as of ${dateLabel(b.as_of)}` : undefined;
        const owe = b.groups.filter((g) => OWE.test(g.name));
        const equity = b.groups.filter((g) => !OWE.test(g.name) && EQUITY.test(g.name));
        const own = b.groups.filter((g) => !owe.includes(g) && !equity.includes(g));
        const receivable = own.find((g) => /receivable|debtor/i.test(g.name));
        return (
          <div className={styles.stack}>
            <div className={styles.opening}>
              <div className={styles.answer}>
                <p className={styles.kicker}>Where the business stands</p>
                <p className={styles.answerLine}>
                  <strong>{money(b.cash_on_hand)}</strong> in the bank and in hand
                  {receivable ? (
                    <>
                      , <strong>{money(receivable.total)}</strong> owed by customers
                    </>
                  ) : null}
                  {owe[0] ? (
                    <>
                      , and <strong>{money(owe[0].total)}</strong> owed in{" "}
                      {owe[0].name.toLowerCase()}
                    </>
                  ) : null}
                  {asOf ? `, ${asOf}.` : "."}
                </p>
                <p className={styles.muted}>Balances as your books group them</p>
              </div>

              <section className={styles.summary} aria-label="Balance summary">
                <Figure
                  label="Cash on hand"
                  value={money(b.cash_on_hand)}
                  basis="balance"
                  window={asOf}
                  context="Bank + cash"
                />
                {receivable ? (
                  <Figure
                    label="Receivables"
                    value={money(receivable.total)}
                    basis="balance"
                    window={asOf}
                    context="Owed by customers"
                  />
                ) : null}
                {owe[0] ? (
                  <Figure
                    label={owe[0].name}
                    value={money(owe[0].total)}
                    basis="balance"
                    window={asOf}
                    context="Largest group of amounts owed"
                  />
                ) : null}
              </section>
            </div>

            <Section
              eyebrow="The statement"
              title="What you own and what you owe"
              description="Early view: what this page should summarise is still being agreed. It lists the balance-sheet lines Clario has read, grouped as your books group them."
              aside={
                <AskLink
                  ask={ask}
                  question="How much cash do we have and what do customers owe us?"
                />
              }
            >
              <div className={styles.sheet}>
                <section className={styles.sheetSide} aria-label="What you own">
                  <div className={styles.sheetHead}>
                    <h3 className={styles.sheetTitle}>What you own</h3>
                    <span className={styles.note}>Cash, money owed to you and other assets</span>
                  </div>
                  {own.length ? (
                    <Statement groups={own} />
                  ) : (
                    <p className={styles.note}>No asset accounts were read.</p>
                  )}
                </section>
                <section className={styles.sheetSide} aria-label="What you owe">
                  <div className={styles.sheetHead}>
                    <h3 className={styles.sheetTitle}>What you owe</h3>
                    <span className={styles.note}>
                      Liabilities and, where the books have it, equity
                    </span>
                  </div>
                  {owe.length || equity.length ? (
                    <Statement groups={[...owe, ...equity]} />
                  ) : (
                    <p className={styles.note}>No liability or equity accounts were read.</p>
                  )}
                </section>
              </div>
            </Section>
          </div>
        );
      }}
    </TabBody>
  );
}
