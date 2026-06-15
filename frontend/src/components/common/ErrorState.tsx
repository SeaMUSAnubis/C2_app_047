interface ErrorStateProps {
  message?: string;
}

export function ErrorState({ message = 'An error occurred' }: ErrorStateProps) {
  return (
    <div className="error-state">
      <h3>Error</h3>
      <p>{message}</p>
    </div>
  );
}
