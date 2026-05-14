export default function RoleBadge({ role }) {
  return <span className={`role-badge role-${role || "unknown"}`}>{role || "unknown"}</span>;
}
