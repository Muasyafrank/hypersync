import { Button } from 'react-bootstrap';
import { AlertTriangle } from 'lucide-react';

/** Inline error with an optional retry. */
export default function ErrorState({ message = 'Something went wrong.', onRetry }) {
  return (
    <div className="hs-empty-state">
      <AlertTriangle size={26} color="#DC2626" className="mb-2" />
      <p className="hs-subtitle mb-0">{message}</p>
      {onRetry && (
        <Button variant="outline-secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
