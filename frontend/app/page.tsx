import Link from "next/link";

const HIGHLIGHTS = [
  {
    label: "Route split",
    value: "/inference",
    detail: "Guided upload, line selection, processing, and report download.",
  },
  {
    label: "Dashboard stub",
    value: "/dashboard",
    detail: "Reserved for the future analytics workspace and task history.",
  },
  {
    label: "Counting model",
    value: "YOLOv10",
    detail: "Vehicle detection with track-level deduplication and direction logic.",
  },
];

const FLOW_STEPS = [
  "Upload the road or drone clip.",
  "Pick two points on frame 20.",
  "Run inference and monitor progress.",
  "Review the annotated video and export the report.",
];

export default function HomePage() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">Smart Drone Traffic Analyzer</p>
          <h1>Traffic analysis with a cleaner entry point and a guided inference flow.</h1>
          <p className="hero-text">
            Start at the landing page, open the inference workflow when you have a video, and keep the dashboard
            reserved for project-level reporting.
          </p>

          <div className="hero-actions">
            <Link className="button-primary" href="/inference">
              Start inference
            </Link>
            <Link className="button-secondary" href="/dashboard">
              View dashboard stub
            </Link>
          </div>
        </div>

        <aside className="hero-sidecard">
          <p className="card-label">Workflow</p>
          <ol className="step-list">
            {FLOW_STEPS.map((step, index) => (
              <li key={step}>
                <span>{index + 1}</span>
                <p>{step}</p>
              </li>
            ))}
          </ol>
        </aside>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <p className="card-label">What changed</p>
          <h2>Navigation is now explicit instead of hidden inside one long page.</h2>
        </div>

        <div className="feature-grid">
          {HIGHLIGHTS.map((item) => (
            <article key={item.label} className="feature-card">
              <p className="card-label">{item.label}</p>
              <h3>{item.value}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
