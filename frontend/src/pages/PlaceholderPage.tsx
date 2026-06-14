import { PageHeader } from '../components/layout/PageHeader';

interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section>
      <PageHeader title={title} description="This module is under development." />
      <div className="empty-state" style={{ marginTop: '24px' }}>
        <h3>Coming Soon</h3>
        <p>This feature will be available in upcoming sprints.</p>
      </div>
    </section>
  );
}
