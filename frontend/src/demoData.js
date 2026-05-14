export const demoPredictions = [
  {
    id: "pred-demo-001",
    document_id: "doc-demo-001",
    source_filename: "invoice_1048.png",
    predicted_class: "invoice",
    top1_confidence: 0.92,
    class_scores: { invoice: 0.92, receipt: 0.06, contract: 0.02 },
    review_eligible: false,
    review_label: null,
    reviewed_at: null,
    created_at: "2026-05-14T09:12:00Z",
  },
  {
    id: "pred-demo-002",
    document_id: "doc-demo-002",
    source_filename: "contract_scan_27.jpg",
    predicted_class: "contract",
    top1_confidence: 0.58,
    class_scores: { contract: 0.58, invoice: 0.31, claim: 0.11 },
    review_eligible: true,
    review_label: null,
    reviewed_at: null,
    created_at: "2026-05-14T09:18:00Z",
  },
  {
    id: "pred-demo-003",
    document_id: "doc-demo-003",
    source_filename: "claim_packet_page_1.png",
    predicted_class: "claim",
    top1_confidence: 0.67,
    class_scores: { claim: 0.67, contract: 0.21, receipt: 0.12 },
    review_eligible: true,
    review_label: null,
    reviewed_at: null,
    created_at: "2026-05-14T09:25:00Z",
  },
];

export const demoUsers = [
  { id: "user-demo-admin", email: "admin@example.com", is_active: true, roles: ["admin"] },
  { id: "user-demo-reviewer", email: "reviewer@example.com", is_active: true, roles: ["reviewer"] },
  { id: "user-demo-auditor", email: "auditor@example.com", is_active: true, roles: ["auditor"] },
];

export const demoAuditEvents = [
  {
    id: "audit-demo-001",
    actor_id: "user-demo-admin",
    action: "roles.replace",
    target_type: "user",
    target_id: "user-demo-reviewer",
    target: "reviewer@example.com",
    outcome: "success",
    timestamp: "2026-05-14T09:02:00Z",
    metadata: { roles: ["reviewer"] },
  },
  {
    id: "audit-demo-002",
    actor_id: "user-demo-reviewer",
    action: "prediction.review",
    target_type: "prediction",
    target_id: "pred-demo-002",
    target: "contract_scan_27.jpg",
    outcome: "success",
    timestamp: "2026-05-14T09:28:00Z",
    metadata: { reviewed_label: "contract" },
  },
];
