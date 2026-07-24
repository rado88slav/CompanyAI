interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({
  title,
  description,
}: PlaceholderPageProps) {
  return (
    <section className="page" aria-labelledby="placeholder-title">
      <div className="page-heading">
        <span className="eyebrow">Future module</span>
        <h1 id="placeholder-title">{title}</h1>
        <p>{description}</p>
      </div>
      <div className="empty-panel">
        <span className="empty-panel__icon" aria-hidden="true">○</span>
        <h2>Not configured yet</h2>
        <p>This module is coming in a later dashboard stage.</p>
      </div>
    </section>
  );
}
