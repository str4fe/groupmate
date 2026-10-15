import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import WebApp from "@twa-dev/sdk";
import {
  api,
  setTokens,
  type Lesson,
  type Mark,
  type Status,
  type StudentMark,
  type User,
} from "./api";
import "./style.css";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready(): void;
        expand(): void;
        HapticFeedback?: { notificationOccurred(type: string): void };
      };
    };
  }
}
const telegramInitData = window.Telegram?.WebApp?.initData || WebApp.initData;
if (telegramInitData) {
  window.Telegram?.WebApp?.ready?.();
  window.Telegram?.WebApp?.expand?.();
}
const localDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const displayDate = (date: string) =>
  new Date(`${date}T12:00:00`).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    weekday: "long",
  });
const labels: Record<Status | "unmarked", string> = {
  present: "Был",
  absent_valid: "Уваж.",
  absent_invalid: "Неуваж.",
  unmarked: "Не отметился",
};
const lessonTypes: Record<string, string> = {
  lecture: "Лекция",
  practice: "Практика",
  lab: "Лабораторная",
};
function message(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Не удалось выполнить действие";
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(telegramInitData));
  const [error, setError] = useState("");
  const [devId, setDevId] = useState("784174718");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"mine" | "admin">("mine");
  const [date, setDate] = useState(localDate());
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [marks, setMarks] = useState<Mark[]>([]);
  const [selectedLesson, setSelectedLesson] = useState<number | null>(null);
  const [roster, setRoster] = useState<StudentMark[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [editing, setEditing] = useState<StudentMark | null>(null);
  const [manualStatus, setManualStatus] = useState<Status>("present");
  const [from, setFrom] = useState(localDate());
  const [to, setTo] = useState(localDate());
  const listRequest = useRef(0);
  const rosterRequest = useRef(0);
  const modal = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!editing) return;
    const previous = document.activeElement as HTMLElement | null;
    const controls =
      modal.current?.querySelectorAll<HTMLElement>("input, button");
    controls?.[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setEditing(null);
      if (event.key === "Tab" && controls?.length) {
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [editing]);

  const loadProfile = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch (e) {
      setTokens(null);
      throw e;
    }
  }, []);
  useEffect(() => {
    if (!telegramInitData) return;
    let active = true;
    (async () => {
      try {
        setTokens(null);
        setTokens(await api.loginTelegram(telegramInitData));
        const profile = await api.me();
        if (active) setUser(profile);
      } catch (e) {
        if (active) {
          setTokens(null);
          setError(message(e));
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const adminView = tab === "admin" && user?.role !== "student";
  const refresh = useCallback(async () => {
    if (!user) return;
    const requestId = ++listRequest.current;
    try {
      const list =
        adminView && date !== localDate()
          ? await api.lessons(date)
          : await api.today();
      if (requestId !== listRequest.current) return;
      setLessons(list);
      if (!adminView) {
        const own = list.filter(
          (l) => l.subgroup === 0 || l.subgroup === user.subgroup,
        );
        setLessons(own);
        const results = await api.myMarks(own[0]?.date ?? localDate());
        if (requestId === listRequest.current) {
          setMarks(results);
          setError("");
        }
      } else
        setSelectedLesson((current) =>
          list.some((l) => l.id === current)
            ? current
            : (list.find((l) => l.status !== "cancelled")?.id ?? null),
        );
      if (adminView) setError("");
    } catch (e) {
      if (requestId === listRequest.current) setError(message(e));
    }
  }, [user, adminView, date]);
  useEffect(() => {
    setLessons([]);
    void refresh();
    const onFocus = () => {
      void refresh();
    };
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 30000);
    return () => {
      ++listRequest.current;
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [refresh]);
  const refreshRoster = useCallback(async () => {
    if (selectedLesson == null || !adminView) return;
    const requestId = ++rosterRequest.current;
    try {
      const results = await api.roster(selectedLesson);
      if (requestId === rosterRequest.current) {
        setRoster(results);
        setSelected([]);
        setError("");
      }
    } catch (e) {
      setError(message(e));
    }
  }, [selectedLesson, adminView]);
  useEffect(() => {
    setRoster([]);
    setSelected([]);
    void refreshRoster();
    return () => {
      ++rosterRequest.current;
    };
  }, [refreshRoster]);

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <main className="shell">
        <div className="panel">Загружаем groupmate…</div>
      </main>
    );
  if (!user)
    return (
      <main className="shell">
        <div className="brand">
          groupmate<span> / mini app</span>
        </div>
        <section className="panel login">
          <div className="icon">↗</div>
          <h1>{telegramInitData ? "Не удалось войти" : "Вход для разработки"}</h1>
          <p>
            {telegramInitData
              ? "Проверьте подключение и регистрацию в группе."
              : "Выберите тестового пользователя или введите Telegram ID. Доступно только при DEBUG_AUTH=true."}
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {!telegramInitData && (
            <>
              <div className="segmented">
                <button
                  className={devId === "784174718" ? "active" : ""}
                  onClick={() => setDevId("784174718")}
                >
                  Староста
                </button>
                <button
                  className={devId === "100000001" ? "active" : ""}
                  onClick={() => setDevId("100000001")}
                >
                  Студент
                </button>
              </div>
              <label className="field">
                Telegram ID
                <input
                  inputMode="numeric"
                  value={devId}
                  onChange={(e) => setDevId(e.target.value)}
                />
              </label>
              <button
                className="primary wide"
                disabled={busy || !/^\d+$/.test(devId)}
                onClick={() =>
                  void act(async () => {
                    setTokens(null);
                    setTokens(await api.loginDev(Number(devId)));
                    await loadProfile();
                  })
                }
              >
                Войти
              </button>
            </>
          )}
          {telegramInitData && (
            <button
              className="primary wide"
              onClick={() => window.location.reload()}
            >
              Повторить
            </button>
          )}
        </section>
      </main>
    );

  const current = lessons.find((l) => l.id === selectedLesson);
  const eligible = roster.filter(
    (s) =>
      current && (current.subgroup === 0 || current.subgroup === s.subgroup),
  );
  const confirmable = eligible.filter(
    (s) => s.status !== "unmarked" && !s.is_confirmed,
  );
  return (
    <main className="shell">
      <header>
        <div className="brand">
          groupmate<span> / посещаемость</span>
        </div>
        <button
          className="text-button"
          onClick={() => {
            setTokens(null);
            setUser(null);
            setTab("mine");
            setMarks([]);
            setEditing(null);
          }}
        >
          Выйти
        </button>
      </header>
      <section className="hero">
        <div className="eyebrow">
          {user.role === "student"
            ? "СТУДЕНТ"
            : user.role === "headman"
              ? "СТАРОСТА"
              : "ЗАМЕСТИТЕЛЬ"}{" "}
          · ПОДГРУППА {user.subgroup}
        </div>
        <h1>{user.full_name}</h1>
        <p>{displayDate(localDate())}</p>
        <div className="hero-mark">
          {user.full_name
            .split(" ")
            .slice(0, 2)
            .map((s) => s[0])
            .join("")}
        </div>
      </section>
      {user.role !== "student" && (
        <nav className="tabs" aria-label="Раздел">
          <button
            className={tab === "mine" ? "active" : ""}
            onClick={() => setTab("mine")}
          >
            Мой чекин
          </button>
          <button
            className={tab === "admin" ? "active" : ""}
            onClick={() => setTab("admin")}
          >
            Управление группой
          </button>
        </nav>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="panel notice" role="status">
          {notice}
        </p>
      )}
      {!adminView ? (
        <section>
          <div className="section-title">
            <div>
              <div className="eyebrow">МОЙ ДЕНЬ</div>
              <h2>Расписание на сегодня</h2>
            </div>
            <span className="count">{lessons.length} пар</span>
          </div>
          {lessons.length === 0 && (
            <div className="panel empty">Сегодня пар нет. Можно выдохнуть.</div>
          )}
          {lessons.map((lesson) => {
            const mark = marks.find((m) => m.lesson_id === lesson.id);
            return (
              <article className="lesson panel" key={lesson.id}>
                <div className="slot">
                  <strong>{String(lesson.slot_number).padStart(2, "0")}</strong>
                  <small>ПАРА</small>
                </div>
                <div className="lesson-body">
                  <div className="lesson-top">
                    <span>
                      {lesson.time_start && lesson.time_end
                        ? `${lesson.time_start} — ${lesson.time_end}`
                        : `${lesson.slot_number}-я пара`}
                    </span>
                    <span className={`badge ${lesson.status}`}>
                      {lesson.status === "cancelled"
                        ? "Отменена"
                        : lesson.status === "completed"
                          ? "Завершена"
                          : "По расписанию"}
                    </span>
                  </div>
                  <h3>{lesson.subject_name}</h3>
                  <p>
                    {lessonTypes[lesson.lesson_type || ""] || "Занятие"} ·{" "}
                    {lesson.subgroup === 0
                      ? "Вся группа"
                      : `${lesson.subgroup} подгруппа`}
                  </p>
                  <div className="divider" />
                  <div className="lesson-footer">
                    <span className={`mark ${mark?.status || ""}`}>
                      {mark
                        ? mark.status === "present"
                          ? mark.is_confirmed
                            ? "✓ Подтверждено старостой"
                            : "◷ Вы отметились (ожидает подтверждения)"
                          : `Пропуск · ${labels[mark.status]}`
                        : "○ Вы ещё не отметились"}
                    </span>
                    {lesson.status !== "cancelled" && !mark && (
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            const result = await api.checkIn(lesson.id);
                            setMarks((previous) => [
                              ...previous.filter(
                                (m) => m.lesson_id !== lesson.id,
                              ),
                              result,
                            ]);
                            window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("success");
                            setNotice(
                              "Вы отметились. Ожидаем подтверждения старосты.",
                            );
                          })
                        }
                      >
                        Отметиться
                      </button>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <section>
          <div className="section-title">
            <div>
              <div className="eyebrow">АДМИНИСТРИРОВАНИЕ</div>
              <h2>Управление группой</h2>
            </div>
          </div>
          <div className="panel controls">
            <label className="field">
              Дата занятия
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label className="field">
              Выберите пару
              <select
                value={selectedLesson ?? ""}
                onChange={(e) => setSelectedLesson(Number(e.target.value))}
              >
                {lessons
                  .filter((l) => l.status !== "cancelled")
                  .map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.slot_number}-я · {l.subject_name}
                      {l.subgroup ? ` · ПГ ${l.subgroup}` : ""}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          {!current ? (
            <div className="panel empty">
              На выбранную дату доступных пар нет.
            </div>
          ) : (
            <>
              <div className="section-title roster-heading">
                <h2>Список группы</h2>
                <span className="count">{eligible.length} чел.</span>
              </div>
              <div className="panel roster">
                <div className="roster-top">
                  <span>СТУДЕНТ</span>
                  <span>СТАТУС</span>
                </div>
                {eligible.map((student) => (
                  <div className="student" key={student.user_id}>
                    <input
                      type="checkbox"
                      aria-label={`Выбрать ${student.full_name}`}
                      disabled={
                        student.status === "unmarked" ||
                        student.is_confirmed ||
                        busy
                      }
                      checked={selected.includes(student.user_id)}
                      onChange={(e) =>
                        setSelected((prev) =>
                          e.target.checked
                            ? [...prev, student.user_id]
                            : prev.filter((id) => id !== student.user_id),
                        )
                      }
                    />
                    <button
                      className="student-name"
                      onClick={() => {
                        setEditing(student);
                        setManualStatus(
                          student.status === "unmarked"
                            ? "present"
                            : student.status,
                        );
                      }}
                    >
                      <strong>{student.full_name}</strong>
                      <small>
                        {student.subgroup} подгруппа · изменить статус
                      </small>
                    </button>
                    <span className={`status ${student.status}`}>
                      {labels[student.status]}
                    </span>
                    {student.is_confirmed && (
                      <span className="confirmed" title="Подтверждено">
                        ✓
                      </span>
                    )}
                  </div>
                ))}
              </div>
              <div className="actions">
                <button
                  className="primary"
                  disabled={busy || !selected.length}
                  onClick={() =>
                    void act(async () => {
                      await api.confirm(current.id, selected);
                      await refreshRoster();
                    })
                  }
                >
                  Подтвердить выбранных ({selected.length})
                </button>
                <button
                  className="secondary"
                  disabled={
                    busy || !confirmable.some((s) => s.status === "present")
                  }
                  onClick={() =>
                    void act(async () => {
                      await api.confirm(
                        current.id,
                        confirmable
                          .filter((s) => s.status === "present")
                          .map((s) => s.user_id),
                      );
                      await refreshRoster();
                    })
                  }
                >
                  Подтвердить всех присутствующих
                </button>
              </div>
            </>
          )}
          <div className="panel export">
            <div>
              <h3>Ведомость посещаемости</h3>
              <p>Экспорт в формате Excel</p>
            </div>
            <div className="date-row">
              <label className="field">
                С
                <input
                  type="date"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
              </label>
              <label className="field">
                По
                <input
                  type="date"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                />
              </label>
            </div>
            <button
              className="secondary wide"
              disabled={busy || from > to}
              onClick={() => void act(() => api.export(from, to))}
            >
              ↓ Скачать ведомость (Excel)
            </button>
          </div>
        </section>
      )}
      {editing && current && (
        <div
          className="overlay"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setEditing(null);
          }}
        >
          <div
            className="modal"
            ref={modal}
            role="dialog"
            aria-modal="true"
            aria-label="Изменить статус"
          >
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div className="eyebrow">РУЧНАЯ ОТМЕТКА</div>
            <h2>{editing.full_name}</h2>
            <p>Выберите статус для занятия «{current.subject_name}».</p>
            <div className="status-options">
              {(["present", "absent_valid", "absent_invalid"] as Status[]).map(
                (status) => (
                  <label key={status}>
                    <input
                      type="radio"
                      name="manual-status"
                      checked={manualStatus === status}
                      onChange={() => setManualStatus(status)}
                    />
                    {labels[status]}
                  </label>
                ),
              )}
            </div>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setEditing(null)}>
                Отмена
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    await api.manual(current.id, editing.user_id, manualStatus);
                    setEditing(null);
                    await refreshRoster();
                  })
                }
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
      <footer>groupmate · рядом с вашей группой</footer>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
