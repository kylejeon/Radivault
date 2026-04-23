import { HospitalSignInForm } from "./HospitalSignInForm";

export default function HospitalSignIn() {
  return (
    <div className="surface-hospital min-h-screen bg-surface-muted">
      <main className="mx-auto max-w-md px-6 py-16">
        <h1 className="text-2xl font-semibold">병원 관리자 로그인</h1>
        <p className="mt-1 text-sm text-ink-muted">
          병원 ID와 관리자 토큰을 입력하세요. 토큰은 RadiVault 담당자로부터 받아야 합니다.
        </p>
        <div className="mt-6">
          <HospitalSignInForm />
        </div>
      </main>
    </div>
  );
}
