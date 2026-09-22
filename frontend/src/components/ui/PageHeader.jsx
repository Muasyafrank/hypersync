import { ArrowLeft } from 'lucide-react';

/** Page title block with optional back arrow and right-hand action. */
export default function PageHeader({ title, subtitle, action, onBack }) {
  return (
    <header className="hs-page-header">
      <div>
        <div className="d-flex align-items-center gap-3">
          {onBack && (
            <button type="button" className="hs-icon-btn" onClick={onBack} aria-label="Go back">
              <ArrowLeft size={20} />
            </button>
          )}
          <h2 className="hs-title mb-0">{title}</h2>
        </div>
        {subtitle && <p className="hs-subtitle mb-0 mt-1">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}
