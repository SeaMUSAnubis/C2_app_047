import type { ReactNode } from 'react';

interface StateMessageProps {
  variant: 'loading' | 'empty' | 'error';
  title?: string;
  children?: ReactNode;
}

export function StateMessage({ variant, title, children }: StateMessageProps) {
  if (variant === 'loading') {
    return <p className="state-message state-loading">{title ?? 'Đang tải dữ liệu...'}</p>;
  }
  if (variant === 'error') {
    return (
      <div className="state-message state-error">
        <h3>{title ?? 'Lỗi'}</h3>
        {children && <p>{children}</p>}
      </div>
    );
  }
  return <p className="state-message state-empty">{children ?? title ?? 'Không có dữ liệu'}</p>;
}
