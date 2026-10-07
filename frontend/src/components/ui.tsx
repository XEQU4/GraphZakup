import type { CSSProperties, ReactNode } from "react";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ExclamationTriangleIcon,
  ReloadIcon,
  MagnifyingGlassIcon,
} from "@radix-ui/react-icons";
import { cx, formatCount } from "../lib/utils";

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: "neutral" | "blue" | "cyan" | "amber" | "danger" | "success";
  className?: string;
}) {
  return (
    <span className={cx("badge", "badge-" + tone, className)}>{children}</span>
  );
}

export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      aria-hidden="true"
      className={cx("skeleton", className)}
      style={style}
    />
  );
}

export function EmptyState({
  title = "No saved records",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-state" role="status">
      <span className="state-icon">
        <MagnifyingGlassIcon aria-hidden="true" />
      </span>
      <h3 className="state-title">{title}</h3>
      <div className="state-copy">
        {children ?? "Try a different search or adjust the filters."}
      </div>
    </div>
  );
}

export function PageState({
  loading,
  error,
  empty = false,
  onRetry,
  emptyTitle,
  emptyMessage,
}: {
  loading?: boolean;
  error?: Error | string | null;
  empty?: boolean;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyMessage?: ReactNode;
}) {
  if (loading)
    return (
      <div
        className="page-state page-state-loading"
        role="status"
        aria-label="Loading saved data"
      >
        <div className="loading-bars" aria-hidden="true">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
        <span className="sr-only">Loading saved data…</span>
      </div>
    );
  if (error)
    return (
      <div className="page-state page-state-error" role="alert">
        <span className="state-icon">
          <ExclamationTriangleIcon aria-hidden="true" />
        </span>
        <h3 className="state-title">Saved data could not be loaded</h3>
        <p className="state-copy">
          {typeof error === "string" ? error : error.message}
        </p>
        {onRetry && (
          <button
            className="button button-secondary"
            type="button"
            onClick={onRetry}
          >
            <ReloadIcon aria-hidden="true" /> Try again
          </button>
        )}
      </div>
    );
  return empty ? (
    <EmptyState title={emptyTitle}>{emptyMessage}</EmptyState>
  ) : null;
}

export function Pagination({
  page,
  total,
  pageSize = 25,
  onPage,
}: {
  page: number;
  total: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav className="pagination" aria-label="Results pagination">
      <span className="pagination-info">
        {formatCount(first)}–{formatCount(last)} of {formatCount(total)}
      </span>
      <div className="pagination-controls">
        <button
          className="icon-button"
          type="button"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPage(Math.max(1, page - 1))}
        >
          <ArrowLeftIcon aria-hidden="true" />
        </button>
        <span>
          Page {formatCount(page)} of {formatCount(pages)}
        </span>
        <button
          className="icon-button"
          type="button"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => onPage(Math.min(pages, page + 1))}
        >
          <ArrowRightIcon aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
