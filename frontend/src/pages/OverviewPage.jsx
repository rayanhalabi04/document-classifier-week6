import FlowStepper from "../components/FlowStepper";
import StatCard from "../components/StatCard";

export default function OverviewPage({ user, data, role }) {
  const reviewNeeded = data.predictions.filter((prediction) => prediction.review_eligible).length;

  return (
    <div className="page-stack">
      <div className="stats-grid">
        <StatCard label="Recent predictions" value={data.predictions.length} note="Latest API window" />
        <StatCard label="Needs review" value={reviewNeeded} note="Low-confidence queue" />
        <StatCard label="Audit events" value={data.auditEvents.length} note="Recent activity" />
        <StatCard label="Current role" value={role} note={user.email} />
      </div>
      <FlowStepper />
    </div>
  );
}
