"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/workflow-utils";

interface BusinessMemory {
  id: number;
  business_id: number | null;
  category: string;
  key: string;
  value: string;
  source: string;
  created_at: string;
  updated_at: string;
}

const CATEGORIES = [
  "general",
  "hours",
  "preferences",
  "clients",
  "services",
  "pricing",
  "policies",
];

export default function MemoryPage() {
  const [memories, setMemories] = useState<BusinessMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [confirmResetAll, setConfirmResetAll] = useState(false);
  const [saving, setSaving] = useState(false);

  // Add form state
  const [newCategory, setNewCategory] = useState("general");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  // Edit form state
  const [editCategory, setEditCategory] = useState("");
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    fetchMemories();
  }, []);

  async function fetchMemories() {
    try {
      const data = await api.get<BusinessMemory[]>("/api/memory");
      setMemories(data);
    } catch {
      // Backend might not be reachable
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd() {
    if (!newKey.trim() || !newValue.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/memory", {
        category: newCategory,
        key: newKey.trim(),
        value: newValue.trim(),
      });
      setNewCategory("general");
      setNewKey("");
      setNewValue("");
      setShowAddForm(false);
      await fetchMemories();
    } catch {
      // Best effort
    } finally {
      setSaving(false);
    }
  }

  function startEdit(mem: BusinessMemory) {
    setEditingId(mem.id);
    setEditCategory(mem.category);
    setEditKey(mem.key);
    setEditValue(mem.value);
  }

  async function handleSaveEdit() {
    if (!editingId || !editKey.trim() || !editValue.trim()) return;
    setSaving(true);
    try {
      await api.patch(`/api/memory/${editingId}`, {
        category: editCategory,
        key: editKey.trim(),
        value: editValue.trim(),
      });
      setEditingId(null);
      await fetchMemories();
    } catch {
      // Best effort
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.delete(`/api/memory/${id}`);
      setConfirmDeleteId(null);
      await fetchMemories();
    } catch {
      // Best effort
    }
  }

  async function handleResetAll() {
    try {
      await api.delete("/api/memory");
      setConfirmResetAll(false);
      await fetchMemories();
    } catch {
      // Best effort
    }
  }

  // Group memories by category
  const grouped: Record<string, BusinessMemory[]> = {};
  for (const mem of memories) {
    if (!grouped[mem.category]) grouped[mem.category] = [];
    grouped[mem.category].push(mem);
  }
  const categories = Object.keys(grouped).sort();

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-stone-900">
            Business Memory
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Things AImplify remembers about your business. You can edit or
            remove anything.
          </p>
        </div>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
          >
            Add Memory
          </button>
        )}
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="mt-4 border border-stone-200 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-stone-900">
            Add New Memory
          </h3>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">
              Category
            </label>
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">
              Label
            </label>
            <input
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder='e.g., "Business hours"'
              className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">
              Value
            </label>
            <textarea
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder='e.g., "9am-5pm EST, Monday through Friday"'
              rows={2}
              className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={saving || !newKey.trim() || !newValue.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => {
                setShowAddForm(false);
                setNewKey("");
                setNewValue("");
              }}
              className="px-4 py-2 text-sm rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <p className="mt-6 text-sm text-stone-400">Loading memories...</p>
      )}

      {/* Empty state */}
      {!loading && memories.length === 0 && (
        <div className="mt-6 border border-dashed border-stone-300 rounded-xl p-8 text-center">
          <p className="text-sm text-stone-500">
            No saved memories yet. As you chat with AImplify, it may suggest
            remembering important details about your business. You can also add
            them manually here.
          </p>
        </div>
      )}

      {/* Grouped memory list */}
      {categories.length > 0 && (
        <div className="mt-6 space-y-6">
          {categories.map((cat) => (
            <div key={cat}>
              <h2 className="text-xs font-semibold text-stone-400 uppercase tracking-wider mb-2">
                {cat}
              </h2>
              <div className="space-y-2">
                {grouped[cat].map((mem) => (
                  <div
                    key={mem.id}
                    className="border border-stone-200 rounded-xl p-4"
                  >
                    {editingId === mem.id ? (
                      /* Edit mode */
                      <div className="space-y-3">
                        <select
                          value={editCategory}
                          onChange={(e) => setEditCategory(e.target.value)}
                          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
                        >
                          {CATEGORIES.map((c) => (
                            <option key={c} value={c}>
                              {c.charAt(0).toUpperCase() + c.slice(1)}
                            </option>
                          ))}
                        </select>
                        <input
                          type="text"
                          value={editKey}
                          onChange={(e) => setEditKey(e.target.value)}
                          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
                        />
                        <textarea
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          rows={2}
                          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none resize-none"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={handleSaveEdit}
                            disabled={
                              saving || !editKey.trim() || !editValue.trim()
                            }
                            className="px-3 py-1.5 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50"
                          >
                            {saving ? "Saving..." : "Save"}
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="px-3 py-1.5 text-sm rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : confirmDeleteId === mem.id ? (
                      /* Delete confirmation */
                      <div className="flex items-center justify-between">
                        <p className="text-sm text-red-600">
                          Delete &ldquo;{mem.key}&rdquo;?
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDelete(mem.id)}
                            className="px-3 py-1.5 text-xs rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 transition-colors"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Display mode */
                      <div>
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-stone-900">
                              {mem.key}
                            </p>
                            <p className="text-sm text-stone-600 mt-0.5">
                              {mem.value}
                            </p>
                          </div>
                          <div className="flex items-center gap-1 ml-3 shrink-0">
                            <button
                              onClick={() => startEdit(mem)}
                              className="p-1.5 text-stone-400 hover:text-stone-600 hover:bg-stone-100 rounded-lg transition-colors"
                              title="Edit"
                            >
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                />
                              </svg>
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(mem.id)}
                              className="p-1.5 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                              title="Delete"
                            >
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <span
                            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                              mem.source === "chat"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-stone-100 text-stone-500"
                            }`}
                          >
                            {mem.source === "chat" ? "via chat" : "manual"}
                          </span>
                          <span className="text-xs text-stone-400">
                            {timeAgo(mem.updated_at)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Reset all */}
      {memories.length > 0 && (
        <div className="mt-8 pt-6 border-t border-stone-200">
          {confirmResetAll ? (
            <div className="flex items-center gap-3">
              <p className="text-sm text-red-600">
                This will delete all {memories.length} memories. Are you sure?
              </p>
              <button
                onClick={handleResetAll}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 transition-colors"
              >
                Yes, reset all
              </button>
              <button
                onClick={() => setConfirmResetAll(false)}
                className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmResetAll(true)}
              className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
            >
              Reset All Memories
            </button>
          )}
        </div>
      )}
    </div>
  );
}
