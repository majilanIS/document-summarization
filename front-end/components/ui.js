import { AlertIcon } from "@/components/icons";

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-primary";

export const buttonSecondary =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink-soft transition-colors hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50";

export function Card({ className = "", children, ...props }) {
  return (
    <section
      className={`rounded-xl border border-line bg-surface ${className}`}
      {...props}
    >
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
    </header>
  );
}

export function ErrorBanner({ message, action }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
    >
      <AlertIcon className="mt-0.5 size-4 shrink-0" />
      <p className="flex-1">{message}</p>
      {action}
    </div>
  );
}

export function Spinner({ className = "size-5" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`${className} animate-spin`}
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="3"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function LoadingBlock({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-20 text-sm text-muted">
      <Spinner className="size-5 text-primary" />
      {label}
    </div>
  );
}
