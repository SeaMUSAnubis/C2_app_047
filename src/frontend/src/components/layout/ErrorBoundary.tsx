import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Lỗi React:', error.message);
    console.error('[ErrorBoundary] Component stack:', info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="page-stack" style={{ padding: '40px 20px', maxWidth: 640, margin: '0 auto' }}>
          <section className="panel-card error-state">
            <h2 style={{ margin: '0 0 12px', color: '#fecdd3' }}>Đã xảy ra lỗi</h2>
            <p style={{ margin: '0 0 16px', color: '#fca5a5' }}>
              Ứng dụng gặp lỗi không mong muốn. Vui lòng thử tải lại trang.
            </p>
            <details style={{ color: '#94a3b8', fontSize: 12 }}>
              <summary>Chi tiết lỗi</summary>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 8 }}>
                {this.state.error?.message}
              </pre>
            </details>
            <button
              className="primary-action"
              style={{ marginTop: 16 }}
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
            >
              Tải lại trang
            </button>
          </section>
        </div>
      );
    }

    return this.props.children;
  }
}
