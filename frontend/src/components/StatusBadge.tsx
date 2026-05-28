import clsx from 'clsx';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const statusStyles: Record<string, string> = {
  pending: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  approved: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  rejected: 'bg-red-50 text-red-700 ring-red-600/20',
  flagged: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  locked: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  completed_with_errors: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  processing: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  failed: 'bg-red-50 text-red-700 ring-red-600/20',
};

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const style = statusStyles[status] || 'bg-slate-50 text-slate-600 ring-slate-500/20';

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium ring-1 ring-inset capitalize',
        style,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      )}
    >
      {status}
    </span>
  );
}
