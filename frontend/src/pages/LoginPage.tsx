/**
 * 로그인 페이지 — Figma 로그인_화면 80% 기준 ver3 (node 3213:34650).
 */
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { isAuthenticated, login } from "../utils/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    const ok = login(userId, password);
    setSubmitting(false);
    if (!ok) {
      setError("회원가입된 계정 정보와 일치하지 않습니다.");
      return;
    }
    navigate("/", { replace: true });
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
          aria-label="로그인"
        >
          <h1 className="mb-[72px] text-[32px] font-bold leading-[1.1] text-black">로그인</h1>

          <div className="w-full max-w-[575px]">
            <label className="block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">ID</span>
              <input
                type="text"
                name="userId"
                autoComplete="username"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            <label className="mt-[38px] block">
              <span className="mb-[9px] block text-base leading-[1.4] text-[#9d9d9d]">Password</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border-0 border-b border-coolgray-30 bg-transparent pb-[11px] text-base text-coolgray-90 outline-none focus:border-primary-60"
                required
              />
            </label>

            {error && (
              <p className="mt-4 text-sm text-alert" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="mt-[44px] h-[60px] w-full rounded-lg bg-primary-60 text-xl font-medium tracking-[0.5px] text-white hover:bg-primary-90 disabled:opacity-50 transition-colors"
            >
              {submitting ? "로그인 중..." : "로그인"}
            </button>

            <Link
              to="/signup"
              className="mt-3 flex h-[54px] w-full items-center justify-center rounded-lg border border-primary-60 bg-white text-lg font-medium tracking-[0.3px] text-primary-60 transition-colors hover:bg-blue-50"
            >
              회원가입
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
