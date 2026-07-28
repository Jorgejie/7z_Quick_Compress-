export function Toast({ toast }) {
  if (!toast) return null;
  return <div className={`toast ${toast.type} show`}>{toast.msg}</div>;
}
