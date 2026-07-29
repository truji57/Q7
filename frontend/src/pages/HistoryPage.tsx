export default function HistoryPage() {
  return (
    <div>
      <h2 className="text-lg font-semibold text-zinc-200 mb-6">Trade History</h2>
      <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-12 text-center">
        <p className="text-zinc-600 text-sm">Trade history will appear here once trading begins.</p>
        <p className="text-zinc-700 text-xs mt-1">Closed trades are auto-logged by the orchestrator.</p>
      </div>
    </div>
  );
}
