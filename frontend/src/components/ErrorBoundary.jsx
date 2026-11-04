import { Component } from 'react';
import { Button, Container } from 'react-bootstrap';
import { AlertTriangle } from 'lucide-react';

/** Catches render-time crashes so a single broken page can't blank the app. */
export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('Unhandled UI error:', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <Container className="py-5 text-center hs-error-boundary">
        <AlertTriangle size={32} color="#DC2626" className="mb-3" />
        <h4 className="hs-title mb-2">Something went wrong</h4>
        <p className="hs-subtitle mb-4">
          The page failed to load. Reloading usually fixes it.
        </p>
        <Button className="btn-hs-primary" onClick={() => window.location.reload()}>
          Reload page
        </Button>
      </Container>
    );
  }
}
