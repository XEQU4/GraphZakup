import { translate as t, useI18n } from "../i18n";
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
  useI18n();
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
  useI18n();
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
  useI18n();
  return (
    <div className="page-state" role="status">
      <span className="state-icon">
        <MagnifyingGlassIcon aria-hidden="true" />
      </span>
      <h3 className="state-title">{t(title)}</h3>
      <div className="state-copy">
        {typeof children === "string"
          ? t(children)
          : (children ?? t("Try a different search or adjust the filters."))}
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
  useI18n();
  if (loading)
    return (
      <div
        className="page-state page-state-loading"
        role="status"
        aria-label={t("Loading saved data")}
      >
        <div className="loading-bars" aria-hidden="true">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
        <span className="sr-only">{t("Loading saved data…")}</span>
      </div>
    );
  if (error)
    return (
      <div className="page-state page-state-error" role="alert">
        <span className="state-icon">
          <ExclamationTriangleIcon aria-hidden="true" />
        </span>
        <h3 className="state-title">{t("Saved data could not be loaded")}</h3>
        <p className="state-copy">
          {t(typeof error === "string" ? error : error.message)}
        </p>
        {onRetry && (
          <button
            className="button button-secondary"
            type="button"
            onClick={onRetry}
          >
            <ReloadIcon aria-hidden="true" /> {t("Try again")}
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
  useI18n();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav className="pagination" aria-label={t("Results pagination")}>
      <span className="pagination-info">
        {t("{first}–{last} of {total}", {
          first: formatCount(first),
          last: formatCount(last),
          total: formatCount(total),
        })}
      </span>
      <div className="pagination-controls">
        <button
          className="icon-button"
          type="button"
          aria-label={t("Previous page")}
          disabled={page <= 1}
          onClick={() => onPage(Math.max(1, page - 1))}
        >
          <ArrowLeftIcon aria-hidden="true" />
        </button>
        <span>
          {t("Page {page} of {pages}", {
            page: formatCount(page),
            pages: formatCount(pages),
          })}
        </span>
        <button
          className="icon-button"
          type="button"
          aria-label={t("Next page")}
          disabled={page >= pages}
          onClick={() => onPage(Math.min(pages, page + 1))}
        >
          <ArrowRightIcon aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
