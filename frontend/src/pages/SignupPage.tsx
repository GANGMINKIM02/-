/**
 * 회원가입 페이지 — LoginPage와 동일한 Figma 레이아웃.
 */
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { isAuthenticated, registerUser } from "../utils/auth";

type SignupForm = {
  name: string;
  email: string;
  password: string;
  passwordConfirm: string;
};

export function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<SignupForm>({
    name: "",
    email: "",
    password: "",
    passwordConfirm: "",
  });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  function onChange<K extends keyof SignupForm>(key: K, value: SignupForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setDone(false);

    if (form.password !== form.passwordConfirm) {
      setError("비밀번호 확인이 일치하지 않습니다.");
      return;
    }

    setSubmitting(true);
    const result = registerUser({
      name: form.name,
      email: form.email,
      password: form.password,
    });
    setSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    setDone(true);
    setTimeout(() => {
      navigate("/login", { replace: true });
    }, 700);
  }

  return (
    <div className="flex min-h-screen bg-coolgray-20">
      <div className="relative hidden min-h-screen flex-1 overflow-hidden lg:block">
        <img
          src="/assets/login-bg.png"
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-cover object-left"
        />
      </div>

      <div className="flex min-h-screen w-full shrink-0 flex-col bg-white lg:w-[845px] lg:max-w-[58.7%] lg:rounded-tl-[50px] lg:rounded-bl-[50px]">
        <form
          onSubmit={handleSubmit}
          className="flex flex-1 flex-col justify-center px-8 py-16 sm:px-16 lg:px-[140px]"
          aria-label="회원가입"
        >
          <h1 className="mb-[56px] text-[32px] font-bold leading-[1.1] text-black">회원가입</h1>

          <div className="w-full max-w-[575px] space-y-[30px]">
            <label className="block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">Name</span>
              <input
                type="text"
                name="name"
                autoComplete="name"
                value={form.name}
                onChange={(e) => onChange("name", e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            <label className="block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">ID</span>
              <input
                type="text"
                name="userId"
                autoComplete="username"
                value={form.email}
                onChange={(e) => onChange("email", e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            <label className="block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">Password</span>
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => onChange("password", e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            <label className="block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">Confirm Password</span>
              <input
                type="password"
                name="passwordConfirm"
                autoComplete="new-password"
                value={form.passwordConfirm}
                onChange={(e) => onChange("passwordConfirm", e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            {error && (
              <p className="text-sm text-alert" role="alert">
                {error}
              </p>
            )}
            {done && (
              <p className="text-sm text-success">회원가입이 완료되었습니다. 로그인 화면으로 이동합니다.</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="h-[60px] w-full rounded-lg bg-primary-60 text-xl font-medium tracking-[0.5px] text-white hover:bg-primary-90 disabled:opacity-50 transition-colors"
            >
              {submitting ? "처리 중..." : "회원가입 완료"}
            </button>

            <Link
              to="/login"
              className="block text-center text-sm font-medium text-primary-60 underline-offset-2 hover:underline"
            >
              로그인으로 돌아가기
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
