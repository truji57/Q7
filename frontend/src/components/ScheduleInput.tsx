import { useState } from 'react';

export default function ScheduleInput({ value, min, max, onSave, className }: {
  value: number;
  min: number;
  max: number;
  onSave: (v: number) => void;
  className?: string;
}) {
  const [local, setLocal] = useState(String(value));

  const commit = () => {
    let n = parseInt(local, 10);
    if (isNaN(n)) n = min;
    n = Math.min(max, Math.max(min, n));
    setLocal(String(n));
    if (n !== value) onSave(n);
  };

  return (
    <input
      type="number"
      min={min}
      max={max}
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
      className={className}
    />
  );
}