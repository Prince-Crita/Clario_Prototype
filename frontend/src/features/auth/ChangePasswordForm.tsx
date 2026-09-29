import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, TextField } from "../../design-system";
import { ApiError } from "../../lib/api/client";
import { useChangePassword } from "./hooks";
import styles from "./ChangePasswordForm.module.css";

const MIN = 12;
const schema = z
  .object({
    current: z.string().min(1, "Enter your current password."),
    next: z
      .string()
      .min(MIN, `Use at least ${MIN} characters.`)
      .max(256, "Use at most 256 characters."),
    confirm: z.string().min(1, "Repeat the new password."),
  })
  .refine((v) => v.next === v.confirm, { path: ["confirm"], message: "The passwords don't match." })
  .refine((v) => v.next !== v.current, {
    path: ["next"],
    message: "Choose a password you haven't used here.",
  });
type FormValues = z.infer<typeof schema>;

export function ChangePasswordForm() {
  const change = useChangePassword();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current: "", next: "", confirm: "" },
  });

  const onSubmit = handleSubmit((values) =>
    change.mutate(
      { current: values.current, next: values.next },
      {
        onSuccess: () => reset(),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "auth.wrong_password") {
            setError("current", { message: error.detail });
          } else if (error instanceof ApiError && error.code === "auth.weak_password") {
            setError("next", { message: error.detail });
          }
        },
      },
    ),
  );

  const generalError =
    change.error instanceof ApiError &&
    !["auth.wrong_password", "auth.weak_password"].includes(change.error.code)
      ? change.error.detail
      : null;

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      {change.isSuccess ? (
        <Alert tone="positive">
          Password changed. You've been signed out on your other devices.
        </Alert>
      ) : null}
      {generalError ? <Alert tone="negative">{generalError}</Alert> : null}
      <TextField
        label="Current password"
        type="password"
        autoComplete="current-password"
        error={errors.current?.message}
        {...register("current")}
      />
      <TextField
        label="New password"
        type="password"
        autoComplete="new-password"
        hint={`At least ${MIN} characters. A short sentence works well.`}
        error={errors.next?.message}
        {...register("next")}
      />
      <TextField
        label="Repeat new password"
        type="password"
        autoComplete="new-password"
        error={errors.confirm?.message}
        {...register("confirm")}
      />
      <div>
        <Button type="submit" variant="primary" pending={change.isPending} pendingLabel="Changing…">
          Change password
        </Button>
      </div>
    </form>
  );
}
