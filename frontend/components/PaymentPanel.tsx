"use client";
import { useEffect, useState } from "react";
import { CreditCard, Plus, Clock, CheckCircle } from "lucide-react";
import { getPayments, createPayment, type Payment } from "@/lib/api";

export default function PaymentPanel({ wallet }: { wallet: string }) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    recipient: "", amount: "100", token: "USDT", schedule: "monthly"
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getPayments(wallet).then(setPayments).catch(console.error);
  }, [wallet]);

  const handleCreate = async () => {
    setSaving(true);
    try {
      await createPayment({ ...form, wallet, amount: parseFloat(form.amount) });
      const updated = await getPayments(wallet);
      setPayments(updated);
      setShowForm(false);
      setForm({ recipient: "", amount: "100", token: "USDT", schedule: "monthly" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2 text-slate-200">
          <CreditCard className="w-4 h-4 text-pink-400" />
          PayFi Automation
        </h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-brand hover:text-brand-light transition-colors"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="space-y-2 bg-surface rounded-lg p-3 animate-fade-in">
          <input
            placeholder="Recipient address"
            value={form.recipient}
            onChange={e => setForm(f => ({ ...f, recipient: e.target.value }))}
            className="w-full bg-surface-card border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand"
          />
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="Amount"
              value={form.amount}
              onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
              className="flex-1 bg-surface-card border border-surface-border text-slate-200 text-xs
                         rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand"
            />
            <select
              value={form.token}
              onChange={e => setForm(f => ({ ...f, token: e.target.value }))}
              className="bg-surface-card border border-surface-border text-slate-200 text-xs
                         rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand"
            >
              {["USDT", "USDC", "ETH"].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <select
            value={form.schedule}
            onChange={e => setForm(f => ({ ...f, schedule: e.target.value }))}
            className="w-full bg-surface-card border border-surface-border text-slate-200 text-xs
                       rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand"
          >
            {["once", "daily", "weekly", "monthly"].map(s => <option key={s}>{s}</option>)}
          </select>
          <button
            onClick={handleCreate}
            disabled={saving || !form.recipient}
            className="w-full bg-pink-500/20 border border-pink-500/40 text-pink-400
                       hover:bg-pink-500/30 text-xs py-1.5 rounded-lg font-medium
                       transition-colors disabled:opacity-50"
          >
            {saving ? "Scheduling..." : "Schedule Payment"}
          </button>
        </div>
      )}

      {/* Payment list */}
      <div className="space-y-2">
        {payments.length === 0 && (
          <p className="text-xs text-slate-500 text-center py-4">
            No scheduled payments. Click + to create one.
          </p>
        )}
        {payments.map(p => (
          <div key={p.id} className="flex items-start gap-2 bg-surface rounded-lg p-2.5">
            {p.status === "active"
              ? <Clock className="w-3.5 h-3.5 text-yellow-400 mt-0.5 flex-shrink-0" />
              : <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 flex-shrink-0" />
            }
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-200 font-mono truncate">
                → {p.recipient.slice(0, 16)}...
              </p>
              <p className="text-xs text-slate-400">
                {p.amount} {p.token} · {p.schedule}
              </p>
              {p.next_execution && (
                <p className="text-xs text-slate-500">
                  Next: {new Date(p.next_execution).toLocaleDateString()}
                </p>
              )}
            </div>
            <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0
              ${p.status === "active" ? "text-yellow-400 bg-yellow-400/10" : "text-green-400 bg-green-400/10"}`}>
              {p.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
