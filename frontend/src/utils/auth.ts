export const USERS_STORAGE_KEY = "easyread-users";
const AUTH_FLAG_KEY = "easyread-auth";
const AUTH_USER_KEY = "easyread-auth-user";

function authStorage(): Storage {
  return sessionStorage;
}

/** 이전 localStorage 세션 키 정리 (탭 종료 시 로그아웃 정책 전환) */
function clearLegacyAuthStorage(): void {
  try {
    localStorage.removeItem(AUTH_FLAG_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  } catch {
    /* ignore */
  }
}

clearLegacyAuthStorage();

export interface StoredUser {
  name: string;
  email: string;
  password: string;
  createdAt: string;
}

export interface AuthSession {
  email: string;
  name: string;
  loggedInAt: number;
}

export function readUsers(): StoredUser[] {
  try {
    const raw = localStorage.getItem(USERS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is StoredUser => {
      if (!item || typeof item !== "object") return false;
      const candidate = item as Partial<StoredUser>;
      return (
        typeof candidate.name === "string" &&
        typeof candidate.email === "string" &&
        typeof candidate.password === "string" &&
        typeof candidate.createdAt === "string"
      );
    });
  } catch {
    return [];
  }
}

export function writeUsers(users: StoredUser[]): void {
  localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(users));
}

export function isAuthenticated(): boolean {
  try {
    return authStorage().getItem(AUTH_FLAG_KEY) === "signed-in";
  } catch {
    return false;
  }
}

export function getAuthUserId(): string | null {
  try {
    const userId = authStorage().getItem(AUTH_USER_KEY);
    return userId?.trim() || null;
  } catch {
    return null;
  }
}

export function getAuthSession(): AuthSession | null {
  if (!isAuthenticated()) return null;
  const email = getAuthUserId();
  if (!email) return null;
  const user = readUsers().find((u) => u.email.toLowerCase() === email.toLowerCase());
  return {
    email,
    name: user?.name ?? email,
    loggedInAt: Date.now(),
  };
}

export function login(userId: string, password: string): boolean {
  const normalized = userId.trim().toLowerCase();
  const matched = readUsers().find(
    (user) => user.email.toLowerCase() === normalized && user.password === password,
  );
  if (!matched) return false;

  clearLegacyAuthStorage();
  authStorage().setItem(AUTH_FLAG_KEY, "signed-in");
  authStorage().setItem(AUTH_USER_KEY, matched.email);
  return true;
}

export function logout(): void {
  clearLegacyAuthStorage();
  authStorage().removeItem(AUTH_FLAG_KEY);
  authStorage().removeItem(AUTH_USER_KEY);
}

export function registerUser(input: {
  name: string;
  email: string;
  password: string;
}): { ok: true } | { ok: false; error: string } {
  const name = input.name.trim();
  const email = input.email.trim().toLowerCase();
  const password = input.password;

  if (!name) return { ok: false, error: "이름을 입력해 주세요." };
  if (!email) return { ok: false, error: "아이디를 입력해 주세요." };
  if (!password) return { ok: false, error: "비밀번호를 입력해 주세요." };

  const users = readUsers();
  if (users.some((user) => user.email.toLowerCase() === email)) {
    return { ok: false, error: "이미 가입된 아이디입니다." };
  }

  users.push({
    name,
    email,
    password,
    createdAt: new Date().toISOString(),
  });
  writeUsers(users);
  return { ok: true };
}

const ADMIN_EMAILS = (import.meta.env.VITE_ADMIN_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

/** .env VITE_ADMIN_EMAILS(쉼표 구분)에 등록된 로그인 아이디 */
export function isAdminUser(): boolean {
  const id = getAuthUserId()?.toLowerCase();
  return Boolean(id && ADMIN_EMAILS.includes(id));
}
