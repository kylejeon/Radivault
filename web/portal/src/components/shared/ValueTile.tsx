/**
 * ValueTile — design-spec-portal-redesign §5.4 ({#value-tile-v1}).
 *
 * Used by:
 *   - Why RadiVault 3-up (variant="icon")
 *   - How It Works 5-step (variant="numbered")
 *   - Security & Compliance 2x2 (variant="icon")
 *
 * The hover treatment only fires when the tile carries a link
 * (`href` prop). Dumb informational tiles stay flat — matches
 * §5.4 "link 없는 카드는 hover 효과 없음".
 */

import Link from "next/link";
import clsx from "clsx";
import type { ReactNode } from "react";

export type ValueTileProps = {
  variant?: "icon" | "numbered";
  step?: number;
  icon?: ReactNode;
  title: string;
  body: string;
  href?: string;
  linkLabel?: string;
  testId?: string;
};

export function ValueTile({
  variant = "icon",
  step,
  icon,
  title,
  body,
  href,
  linkLabel,
  testId,
}: ValueTileProps) {
  const Wrapper: React.ElementType = href ? Link : "div";
  const wrapperProps = href ? { href } : {};

  return (
    <Wrapper
      {...wrapperProps}
      data-testid={testId}
      className={clsx(
        "block rounded-lg border border-border bg-bg p-6 shadow-card transition-all",
        href &&
          "hover:-translate-y-px hover:border-primary-600 hover:shadow-overlay focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-600/40",
      )}
    >
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-md bg-primary-50 text-primary-700">
        {variant === "numbered" && step !== undefined ? (
          <span className="text-base font-semibold">{step}</span>
        ) : (
          icon ?? <DefaultGlyph />
        )}
      </div>
      <h3 className="text-2xl font-semibold text-text">{title}</h3>
      <p className="mt-3 text-base text-text-muted">{body}</p>
      {href && linkLabel && (
        <span className="mt-4 inline-block text-sm font-medium text-primary-600">
          {linkLabel} <span aria-hidden>→</span>
        </span>
      )}
    </Wrapper>
  );
}

function DefaultGlyph() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M10 2L3 6v6l7 4 7-4V6l-7-4Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
