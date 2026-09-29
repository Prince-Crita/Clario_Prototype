import { Link } from "react-router";

import { Lockup } from "../brand/Wordmark";
import styles from "./NotFound.module.css";

interface NotFoundProps {
  title?: string;
  message?: string;
}

export function NotFound({
  title = "Page not found",
  message = "The address may be mistyped, or the page may have moved.",
}: NotFoundProps) {
  return (
    <main className={styles.page}>
      <Lockup />
      <h1 className={styles.title}>{title}</h1>
      <p className={styles.message}>{message}</p>
      <Link to="/w">Go to your workspaces</Link>
    </main>
  );
}
