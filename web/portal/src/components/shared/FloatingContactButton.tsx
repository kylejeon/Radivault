/**
 * FloatingContactButton — design-spec §19.2 / FR-HO-10.
 *
 * Korean-page-only floating "1:1 문의" button anchored at bottom-right.
 * Closed state = 56×56 teal circle. Open state = 280×180 popover with
 * KakaoTalk + Email choices (K-14 default = both).
 *
 * Accessibility:
 *  - Button has aria-haspopup / aria-expanded / aria-controls.
 *  - Popover is role="dialog" + aria-modal="true" with a focus trap.
 *  - ESC closes; the trigger receives focus on close.
 *  - First action in the popover gets autofocus on open.
 *
 * Render gate (variant="korean"): the component itself does no path
 * inspection — the page is responsible for mounting it only on Korean
 * surfaces (`/ko/*`, `/hospital/*`). That keeps the component pure
 * (no `usePathname` import → no hydration drift).
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { getDict } from "@/lib/i18n";

export type ContactChannel = "kakao" | "email";

export function FloatingContactButton({
  channels = ["kakao", "email"], // K-14 default = both
  kakaoUrl = "https://pf.kakao.com/_radivault",
  emailAddress, // overridden by i18n if absent
  testId = "floating-contact-button",
}: {
  channels?: ReadonlyArray<ContactChannel>;
  kakaoUrl?: string;
  emailAddress?: string;
  testId?: string;
}) {
  const dict = getDict("ko");
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const firstActionRef = useRef<HTMLAnchorElement | null>(null);
  const popoverId = "floating-contact-popover";

  const close = useCallback(() => {
    setOpen(false);
    // Restore focus to the trigger so keyboard users return to context.
    triggerRef.current?.focus();
  }, []);

  // ESC + outside-click handlers — only mounted while the popover is open.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
      if (e.key === "Tab" && popoverRef.current) {
        const focusables = popoverRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    function onClickOut(e: MouseEvent) {
      const target = e.target as Node | null;
      if (
        popoverRef.current &&
        target &&
        !popoverRef.current.contains(target) &&
        triggerRef.current !== target
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClickOut);
    // Autofocus the first action.
    queueMicrotask(() => firstActionRef.current?.focus());
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClickOut);
    };
  }, [open, close]);

  const showKakao = channels.includes("kakao");
  const showEmail = channels.includes("email");
  const email = emailAddress ?? dict.hospital.contactButton.emailAddress;

  return (
    <div
      data-testid={testId}
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3"
    >
      {open ? (
        <div
          ref={popoverRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={`${popoverId}-title`}
          id={popoverId}
          data-testid={`${testId}-popover`}
          className="w-[280px] rounded-md border border-border bg-white p-4 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between">
            <span
              id={`${popoverId}-title`}
              className="text-sm font-semibold text-text-strong"
            >
              {dict.hospital.contactButton.cardTitle}
            </span>
            <button
              type="button"
              onClick={close}
              aria-label={dict.hospital.contactButton.close}
              className="text-text-muted hover:text-text"
            >
              ✕
            </button>
          </div>
          <ul className="flex flex-col gap-2">
            {showKakao ? (
              <li>
                <a
                  ref={firstActionRef}
                  href={kakaoUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  data-testid={`${testId}-kakao`}
                  className="block rounded-md border border-border px-3 py-2 hover:border-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
                >
                  <span className="text-sm font-medium text-text">
                    💬 {dict.hospital.contactButton.kakao}
                  </span>
                  <span className="block text-xs text-text-muted">
                    {dict.hospital.contactButton.kakaoChannel}
                  </span>
                </a>
              </li>
            ) : null}
            {showEmail ? (
              <li>
                <a
                  ref={showKakao ? undefined : firstActionRef}
                  href={`mailto:${email}`}
                  data-testid={`${testId}-email`}
                  className="block rounded-md border border-border px-3 py-2 hover:border-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
                >
                  <span className="text-sm font-medium text-text">
                    ✉ {dict.hospital.contactButton.email}
                  </span>
                  <span className="block text-xs text-text-muted">{email}</span>
                </a>
              </li>
            ) : null}
          </ul>
          <div className="mt-3 text-[11px] text-text-muted">
            {dict.hospital.contactButton.hours}
          </div>
        </div>
      ) : null}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((s) => !s)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={popoverId}
        aria-label={
          open
            ? dict.hospital.contactButton.close
            : dict.hospital.contactButton.open
        }
        title={dict.hospital.contactButton.label}
        data-testid={`${testId}-trigger`}
        className={clsx(
          "flex size-14 items-center justify-center rounded-full bg-teal-600 text-white shadow-lg",
          "hover:bg-teal-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-300",
        )}
      >
        <span aria-hidden className="text-2xl">💬</span>
      </button>
    </div>
  );
}
