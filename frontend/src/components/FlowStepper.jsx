const steps = [
  ["SFTP Drop", "Vendor scanner places image files"],
  ["Ingestion Worker", "Uploads to MinIO and prepares documents"],
  ["Queue", "Classification jobs wait for inference"],
  ["Inference Worker", "Model predicts document class"],
  ["Prediction", "Scores are saved to the database"],
  ["Review/API", "Users browse, review, and audit"],
];

export default function FlowStepper() {
  return (
    <section className="card flow-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">System flow</p>
          <h2>From scanner drop to reviewed prediction</h2>
        </div>
      </div>
      <div className="flow-stepper">
        {steps.map(([title, text], index) => (
          <article className="flow-step" key={title}>
            <div className="flow-index">{index + 1}</div>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
