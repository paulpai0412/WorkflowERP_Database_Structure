interface RecommendationListProps {
  title: string;
  items?: string[];
}

export default function RecommendationList({ title, items = [] }: RecommendationListProps) {
  return (
    <article className="panel report-section recommendation-list">
      <p className="eyebrow">Recommendations</p>
      <h2>{title}</h2>
      {items.length > 0 ? (
        <ol>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      ) : (
        <p className="muted">尚無建議事項。</p>
      )}
    </article>
  );
}
