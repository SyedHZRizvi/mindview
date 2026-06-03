// functions/api/unit-progress.js
// ─────────────────────────────────────────────────────────────────────────────
// Sequential unit-progression system for MindView Academy.
//
// Students must complete units in order. Each unit requires:
//   • AS Practice Quiz — auto-recorded by client JS when student answers all Qs
//   • FOR Diagnostic   — teacher marks "reviewed" in admin progress panel
//   • OF Unit Test     — teacher marks "passed" in admin; this UNLOCKS next unit
//
// Final Exam unlocks only when teacher explicitly grants it (after all OFs passed).
//
// KV schema (stored in USERS_KV):
//   progress:{studentId}:{courseCode}
//   → {
//       ch1: { as_done: bool, for_done: bool, of_passed: bool, unlocked_next: bool },
//       ch2: { ... },
//       ...
//       final_unlocked: bool,
//     }
//
// Endpoints
// ─────────
//   GET  /api/unit-progress?course=eng4u
//        Returns the calling student's full progress for a course.
//        Teachers/admins: add &studentId=X to fetch another user's progress.
//
//   POST /api/unit-progress
//        { action: "as_done", course, chapterNum }         ← student (auto)
//        { action: "mark_for", course, chapterNum, studentId, done }   ← teacher
//        { action: "mark_of",  course, chapterNum, studentId, passed } ← teacher
//        { action: "unlock_final", course, studentId }     ← teacher
//        { action: "reset_chapter", course, chapterNum, studentId }    ← admin only
//
// Owner-approved 2026-06-03.
// ─────────────────────────────────────────────────────────────────────────────

import { readSessionFromRequest } from '../lib/session.js';

const ROLE_RANK = { student: 0, teacher: 1, admin: 2, superuser: 3 };

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

function progressKey(studentId, course) {
  return `progress:${studentId}:${course.toLowerCase()}`;
}

async function getProgress(kv, studentId, course) {
  const key = progressKey(studentId, course);
  const data = await kv.get(key, 'json');
  return data || {};
}

async function saveProgress(kv, studentId, course, data) {
  const key = progressKey(studentId, course);
  await kv.put(key, JSON.stringify(data));
}

// Lookup a student by email → returns their user record.
async function findStudentByEmail(kv, email) {
  const list = await kv.list();
  for (const k of list.keys) {
    if (k.name.startsWith('unlock-') || k.name.startsWith('progress:')) continue;
    const rec = await kv.get(k.name, 'json');
    if (rec && rec.email && rec.email.toLowerCase() === email.toLowerCase()) return rec;
  }
  return null;
}

export async function onRequest(context) {
  const { request, env } = context;

  if (!env.SESSION_SECRET) return json(500, { error: 'SESSION_SECRET not configured' });
  if (!env.USERS_KV)       return json(503, { error: 'USERS_KV not configured' });

  const session = await readSessionFromRequest(request, env.SESSION_SECRET);
  if (!session) return json(401, { error: 'Authentication required' });

  const { role, sub: userId, email } = session;
  const isInstructor = ROLE_RANK[role] >= ROLE_RANK.teacher;
  const isAdmin = ROLE_RANK[role] >= ROLE_RANK.admin;

  const method = request.method.toUpperCase();
  const url = new URL(request.url);

  // ── GET — fetch progress ──────────────────────────────────────────────────
  if (method === 'GET') {
    const course = url.searchParams.get('course');
    if (!course) return json(400, { error: 'course required' });

    // Students only see their own; teachers can see any student
    const targetId = isInstructor ? (url.searchParams.get('studentId') || userId) : userId;
    if (!isInstructor && targetId !== userId) return json(403, { error: 'Forbidden' });

    const progress = await getProgress(env.USERS_KV, targetId, course);
    return json(200, { progress, studentId: targetId });
  }

  // ── POST — record progress ────────────────────────────────────────────────
  if (method === 'POST') {
    let body;
    try { body = await request.json(); } catch { return json(400, { error: 'Invalid JSON' }); }

    const { action, course, chapterNum, studentId: targetId, done, passed } = body || {};
    if (!action || !course) return json(400, { error: 'action and course required' });

    // ── Student: auto-record AS quiz completion ──
    if (action === 'as_done') {
      if (!chapterNum) return json(400, { error: 'chapterNum required' });
      const progress = await getProgress(env.USERS_KV, userId, course);
      const key = `ch${chapterNum}`;
      if (!progress[key]) progress[key] = {};
      progress[key].as_done = true;
      progress[key].as_done_at = new Date().toISOString();
      await saveProgress(env.USERS_KV, userId, course, progress);
      return json(200, { ok: true });
    }

    // ── Teacher: mark FOR as reviewed ──
    if (action === 'mark_for') {
      if (!isInstructor) return json(403, { error: 'Teachers only' });
      if (!chapterNum || !targetId) return json(400, { error: 'chapterNum and studentId required' });

      const progress = await getProgress(env.USERS_KV, targetId, course);
      const key = `ch${chapterNum}`;
      if (!progress[key]) progress[key] = {};
      progress[key].for_done = done !== false; // default true
      progress[key].for_done_by = email;
      progress[key].for_done_at = new Date().toISOString();
      await saveProgress(env.USERS_KV, targetId, course, progress);
      return json(200, { ok: true });
    }

    // ── Teacher: mark OF as passed (also unlocks next unit) ──
    if (action === 'mark_of') {
      if (!isInstructor) return json(403, { error: 'Teachers only' });
      if (!chapterNum || !targetId) return json(400, { error: 'chapterNum and studentId required' });

      const progress = await getProgress(env.USERS_KV, targetId, course);
      const key = `ch${chapterNum}`;
      if (!progress[key]) progress[key] = {};
      progress[key].of_passed = passed !== false; // default true
      progress[key].of_passed_by = email;
      progress[key].of_passed_at = new Date().toISOString();

      if (passed !== false) {
        // Mark this unit as complete → next chapter is implicitly unlocked
        progress[key].completed = true;
        progress[key].completed_at = new Date().toISOString();
      } else {
        progress[key].completed = false;
        progress[key].of_passed = false;
      }

      await saveProgress(env.USERS_KV, targetId, course, progress);
      return json(200, { ok: true, unlockedNext: passed !== false });
    }

    // ── Teacher: unlock final exam ──
    if (action === 'unlock_final') {
      if (!isInstructor) return json(403, { error: 'Teachers only' });
      if (!targetId) return json(400, { error: 'studentId required' });

      const progress = await getProgress(env.USERS_KV, targetId, course);
      progress.final_unlocked = true;
      progress.final_unlocked_by = email;
      progress.final_unlocked_at = new Date().toISOString();
      await saveProgress(env.USERS_KV, targetId, course, progress);
      return json(200, { ok: true });
    }

    // ── Admin: reset a chapter (e.g. student retakes an exam) ──
    if (action === 'reset_chapter') {
      if (!isAdmin) return json(403, { error: 'Admins only' });
      if (!chapterNum || !targetId) return json(400, { error: 'chapterNum and studentId required' });

      const progress = await getProgress(env.USERS_KV, targetId, course);
      const key = `ch${chapterNum}`;
      delete progress[key];
      // Also clear final unlock if resetting any chapter
      delete progress.final_unlocked;
      await saveProgress(env.USERS_KV, targetId, course, progress);
      return json(200, { ok: true });
    }

    return json(400, { error: `Unknown action: ${action}` });
  }

  return json(405, { error: 'Method not allowed' });
}
