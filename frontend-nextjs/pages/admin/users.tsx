import React, { useCallback, useEffect, useState } from "react";
import { authFetch } from "@/lib/auth-headers";
import { useRouter } from "next/router";
import { getAuthToken } from "@/lib/identity";

/**
 * Admin — User Management (gap #3).
 * Employees are provisioned HERE, not by self-registration: an admin
 * creates accounts with a role; self-registration stays available for
 * dev but the pilot disables it (see gap analysis).
 * Backend: /api/admin/users (GET/POST/PATCH/DELETE) + /api/admin/roles.
 */

type AdminUser = {
  id: string;
  email: string;
  username?: string;
  full_name?: string;
  is_active: boolean;
  role?: string | { name?: string };
  created_at?: string;
};

type AdminRole = { id: string; name: string; description?: string };

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function AdminUsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", full_name: "", role: "" });

  const authHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${getAuthToken() || ""}`,
  }), []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [uRes, rRes] = await Promise.all([
        authFetch(`${API}/api/admin/users`, { headers: authHeaders() }),
        authFetch(`${API}/api/admin/roles`, { headers: authHeaders() }),
      ]);
      if (uRes.status === 401 || uRes.status === 403) {
        setError("Admin access required. Sign in with an admin account.");
        return;
      }
      const userData = await uRes.json();
      setUsers(Array.isArray(userData) ? userData : (userData?.users ?? []));
      if (rRes.ok) {
        const roleData = await rRes.json();
        setRoles(Array.isArray(roleData) ? roleData : (roleData?.roles ?? []));
      }
    } catch (e) {
      setError(`Failed to load users: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => { load(); }, [load]);

  const createUser = async () => {
    setNotice(null);
    setError(null);
    if (!form.email || !form.password) {
      setError("Email and initial password are required.");
      return;
    }
    try {
      const res = await authFetch(`${API}/api/admin/users`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          full_name: form.full_name || undefined,
          role_name: form.role || undefined,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        setError(`Create failed (${res.status}): ${body.slice(0, 200)}`);
        return;
      }
      setNotice(`Created ${form.email}. Share the initial password; they can change it under Settings → Account.`);
      setForm({ email: "", password: "", full_name: "", role: "" });
      setCreating(false);
      load();
    } catch (e) {
      setError(`Create failed: ${String(e)}`);
    }
  };

  const toggleActive = async (u: AdminUser, makeActive: boolean) => {
    try {
      const res = await authFetch(`${API}/api/admin/users/${u.id}`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ is_active: makeActive }),
      });
      if (!res.ok) {
        setError(`Update failed (${res.status})`);
        return;
      }
      load();
    } catch (e) {
      setError(`Update failed: ${String(e)}`);
    }
  };

  const roleName = (r: AdminUser["role"]) =>
    typeof r === "string" ? r : r?.name || "—";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 lg:p-10">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">User Management</h1>
            <p className="text-sm text-gray-400">
              Provision employee accounts and roles. Pilot practice: create accounts here; self-registration is disabled.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCreating((v) => !v)}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-sm font-medium"
            >
              {creating ? "Cancel" : "+ Add employee"}
            </button>
            <button
              onClick={() => router.push("/dashboard")}
              className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm"
            >
              Back
            </button>
          </div>
        </div>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-900/40 border border-red-700 text-sm">{error}</div>}
        {notice && <div className="mb-4 p-3 rounded-lg bg-emerald-900/40 border border-emerald-700 text-sm">{notice}</div>}

        {creating && (
          <div className="mb-6 p-4 rounded-xl bg-gray-900 border border-gray-800 grid gap-3 sm:grid-cols-2">
            <input
              className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm"
              placeholder="email@brennan.ca"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <input
              className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm"
              placeholder="Initial password"
              type="text"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <input
              className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm"
              placeholder="Full name (optional)"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
            <select
              className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="">Role (default)</option>
              {roles.map((r) => (
                <option key={r.id} value={r.name}>{r.name}</option>
              ))}
            </select>
            <div className="sm:col-span-2">
              <button
                onClick={createUser}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
              >
                Create account
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : (
          <div className="rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 text-gray-400">
                <tr>
                  <th className="text-left px-4 py-3">Employee</th>
                  <th className="text-left px-4 py-3">Role</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-gray-800 bg-gray-950">
                    <td className="px-4 py-3">
                      <div className="font-medium">{u.full_name || u.username || u.email}</div>
                      <div className="text-xs text-gray-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">{roleName(u.role)}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        u.is_active ? "bg-emerald-900/50 text-emerald-300" : "bg-gray-800 text-gray-400"
                      }`}>
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => toggleActive(u, !u.is_active)}
                        className="px-3 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs"
                      >
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No users found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
