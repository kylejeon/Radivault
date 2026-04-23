export function HospitalHeader({ hospitalId }: { hospitalId: string }) {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  return (
    <header className="border-b border-surface-border bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="size-7 rounded bg-primary" aria-hidden />
          <div>
            <div className="text-sm font-semibold">RadiVault 병원 대시보드</div>
            <div className="text-xs text-ink-subtle">
              병원 코드: <code className="font-mono">{hospitalId}</code>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-ink-muted">
          <span>마지막 업데이트 {hh}:{mm}</span>
          <form action="/api/hospital/session/delete" method="post">
            <button
              type="submit"
              className="rounded-md border border-surface-border px-3 py-1.5 hover:bg-surface-muted"
            >
              로그아웃
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
