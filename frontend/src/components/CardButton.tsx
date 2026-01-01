type Props = {
  disabled?: boolean;
  selected?: boolean;
  label: string;
  onClick: () => void;
};

export function CardButton({ disabled, selected, label, onClick }: Props) {
  const base =
    "rounded border px-2 py-1 text-sm text-left hover:bg-gray-50";
  const cls = selected
    ? `${base} border-blue-500 bg-blue-50`
    : `${base} border-gray-300 bg-white`;

  return (
    <button
      className={cls}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}