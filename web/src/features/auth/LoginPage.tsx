import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";


import { Lockup } from "../../brand/Wordmark";
import { Alert } from "../../design-system/primitives/Alert";
import { Button } from "../../design-system/primitives/Button";
import { TextField } from "../../design-system/primitives/TextField";
import { ApiError } from "../../lib/api/client";
import { safeNext } from "../../lib/labels";
import { useSession, useSignIn } from "./hooks";
import styles from "./LoginPage.module.css";


// The rules a form must satisfy before it can be submitted.
const schema = z.object({
  email: z.string().trim().min(1, "Enter your email address.").email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type FormValues = z.infer<typeof schema>;

/** True when the backend rejected the email address itself (HTTP 422, field "email"). */
function isEmailFieldError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 422 &&
    error.fields.some((field) => field.field === "email")
  );
}

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
   const signIn = useSignIn();
  const session = useSession();


  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
    } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  // Already signed in: the login form has nothing to offer.
  if (session.data) return <Navigate to={next} replace />;

  // handleSubmit runs the validation first; our function only runs if the form is valid.
  const onSubmit = handleSubmit((values) =>
    signIn.mutate(values, {
      onSuccess: () => navigate(next, { replace: true }),
      onError: (error) => {
        // A malformed email belongs under the Email field, not in the alert.
        if (isEmailFieldError(error)) {
          setError("email", { type: "server", message: "Enter a valid email address." });
        }
      },
    }),
  );

  // 401 → "Invalid email or password."; network → "Clario can't be reached…"; anything else generic.
  const serverError =
    signIn.error && !isEmailFieldError(signIn.error)
      ? signIn.error instanceof ApiError
        ? signIn.error.detail
        : "Sign-in failed. Try again."
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
