import Link from "next/link";

const DASHBOARD_METRICS = [
  { label: "Processed jobs", value: "0", detail: "Ready for persisted task history later." },
  { label: "Retention window", value: "24h", detail: "Matches the current artifact policy in the backend." },
  { label: "Exports", value: "CSV / XLSX", detail: "Report format remains selectable at download time." },
];

export default function DashboardPage() {
  return (
    <div className="page-stack">
      <section className="workspace-banner">
        <div>
          <p className="eyebrow">Dashboard stub</p>
          <h1>A placeholder analytics surface for future task history and reporting.</h1>
          <p className="hero-text">
            The workflow is split now, but the heavier dashboard work is intentionally left as a stub until task
            persistence and user-owned history are in place.
          </p>
        </div>

        <div className="workspace-links">
          <Link className="button-primary" href="/inference">
            Open inference flow
          </Link>
          <Link className="button-secondary" href="/">
            Back to home
          </Link>
        </div>
      </section>

      <section className="section-block">
        <div className="feature-grid dashboard-grid">
          {DASHBOARD_METRICS.map((item) => (
            <article key={item.label} className="feature-card">
              <p className="card-label">{item.label}</p>
              <h3>{item.value}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>

        <article className="panel dashboard-note">
          <h2>What belongs here later</h2>
          <p>
            Task timelines, per-scene summaries, download history, failure analytics, and cleanup visibility are the
            next logical additions once backend persistence exists.
          </p>
        </article>
      </section>
    </div>
  );
}