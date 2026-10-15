export type Role = "student" | "headman" | "deputy";
export type Status = "present" | "absent_valid" | "absent_invalid";
export type User = {
  id: number;
  telegram_id: number;
  full_name: string;
  role: Role;
  subgroup: number;
};
export type Lesson = {
  id: number;
  date: string;
  slot_number: number;
  subject_name: string;
  subgroup: number;
  status: "scheduled" | "completed" | "cancelled";
  time_start: string | null;
  time_end: string | null;
  lesson_type: string | null;
};
export type Mark = {
  lesson_id: number;
  user_id: number;
  status: Status;
  check_in_time: string | null;
  is_confirmed: boolean;
};
export type StudentMark = Omit<Mark, "lesson_id" | "status"> & {
  full_name: string;
  subgroup: number;
  status: Status | "unmarked";
};
type Tokens = { access_token: string; refresh_token: string };

const key = "groupmate.auth";
export function getTokens(): Tokens | null {
  try {
    const value = sessionStorage.getItem(key);
    return value ? (JSON.parse(value) as Tokens) : null;
  } catch {
    return null;
  }
}
export function setTokens(tokens: Tokens | null) {
  if (tokens) sessionStorage.setItem(key, JSON.stringify(tokens));
  else sessionStorage.removeItem(key);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
  binary = false,
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getTokens()?.access_token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  if (
    response.status === 401 &&
    retry &&
    getTokens()?.refresh_token &&
    path !== "/auth/refresh" &&
    !path.startsWith("/auth/")
  ) {
    try {
      const fresh = await request<{ access_token: string }>(
        "/auth/refresh",
        {
          method: "POST",
          body: JSON.stringify({ refresh_token: getTokens()!.refresh_token }),
        },
        false,
      );
      setTokens({ ...getTokens()!, access_token: fresh.access_token });
      return request<T>(path, options, false, binary);
    } catch {
      setTokens(null);
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      typeof body.detail === "string"
        ? body.detail
        : `Ошибка сервера (${response.status})`,
    );
  }
  return (binary ? response.blob() : response.json()) as Promise<T>;
}

export const api = {
  loginTelegram: (init_data: string) =>
    request<Tokens>("/auth/telegram-webapp", {
      method: "POST",
      body: JSON.stringify({ init_data }),
    }),
  loginDev: (telegram_id: number) =>
    request<Tokens>("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ telegram_id }),
    }),
  me: () => request<User>("/users/me"),
  today: () => request<Lesson[]>("/lessons/today"),
  lessons: (date: string) =>
    request<Lesson[]>(`/lessons?date=${encodeURIComponent(date)}`),
  myMarks: (date: string) =>
    request<Mark[]>(`/attendance/me?date=${encodeURIComponent(date)}`),
  checkIn: (lesson_id: number) =>
    request<Mark>("/attendance/check-in", {
      method: "POST",
      body: JSON.stringify({ lesson_id, status: "present" }),
    }),
  roster: (id: number) =>
    request<StudentMark[]>(`/admin/attendance/lesson/${id}`),
  confirm: (lesson_id: number, user_ids: number[]) =>
    request<{ confirmed: number }>("/admin/attendance/confirm", {
      method: "POST",
      body: JSON.stringify({ lesson_id, user_ids }),
    }),
  manual: (lesson_id: number, user_id: number, status: Status) =>
    request<Mark>("/admin/attendance/manual", {
      method: "PUT",
      body: JSON.stringify({ lesson_id, user_id, status }),
    }),
  async export(date_from: string, date_to: string) {
    const blob = await request<Blob>(
      `/admin/attendance/export/excel?${new URLSearchParams({ date_from, date_to })}`,
      {},
      true,
      true,
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `attendance_${date_from}_${date_to}.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },
};
