export default function StatCard({ label, value, note }) {
  return (
    <section className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </section>
  );
}
