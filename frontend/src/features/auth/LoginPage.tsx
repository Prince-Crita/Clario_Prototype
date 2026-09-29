import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { Lockup } from "../../brand/Wordmark";
import { Alert, Button, TextField } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import { safeNext } from "../../lib/labels";
import { useSession, useSignIn } from "./hooks";
import styles from "./LoginPage.module.css";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email address."),
  password: z.string().min(1, "Enter your password."),
});
type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const session = useSession();
  const signIn = useSignIn();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  if (session.data) return <Navigate to={next} replace />;

  const onSubmit = handleSubmit((values) =>
    signIn.mutate(values, { onSuccess: () => navigate(next, { replace: true }) }),
  );
  const serverError =
    signIn.error instanceof ApiError
      ? signIn.error.detail
      : signIn.error
        ? "Sign-in failed. Try again."
        : null;

  return (
    <main className={styles.page}>
      <div className={styles.column}>
        <Lockup size="lg" />
        <section className={styles.panel} aria-labelledby="sign-in-title">
          <div className={styles.intro}>
            <h1 id="sign-in-title" className={styles.title}>
              Sign in
            </h1>
            <p className={styles.lead}>
              Use the email address your workspace administrator set up for you.
            </p>
          </div>
          {serverError ? <Alert tone="negative">{serverError}</Alert> : null}
          <form className={styles.form} onSubmit={onSubmit} noValidate>
            <TextField
              label="Email"
              type="email"
              autoComplete="username"
              inputMode="email"
              autoFocus
              error={errors.email?.message}
              {...register("email")}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              error={errors.password?.message}
              {...register("password")}
            />
            <Button
              type="submit"
              variant="primary"
              block
              pending={signIn.isPending}
              pendingLabel="Signing in…"
            >
              Sign in
            </Button>
          </form>
          <p className={styles.help}>
            Forgot your password? Ask your workspace administrator to reset it.
          </p>
        </section>
        <footer className={styles.footer}>A Crita product</footer>
      </div>
    </main>
  );
}
