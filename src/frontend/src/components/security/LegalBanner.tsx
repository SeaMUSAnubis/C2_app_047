import { ScrollText } from 'lucide-react';

export interface LegalBannerProps {
  /** Override the default Vietnamese text. */
  children?: React.ReactNode;
  /** Compact mode renders a single line; full mode shows multi-line legal text. */
  variant?: 'compact' | 'full';
  /** Optional className passthrough. */
  className?: string;
}

const DEFAULT_FULL = (
  <>
    <strong>Giám sát hành vi người dùng &amp; thiết bị</strong>
    <span>
      Hệ thống Vespionage thu thập log hành vi (logon, USB, file, web, email, process, network) từ
      các máy tính do công ty cấp phát, nhằm phát hiện hành vi bất thường và mối đe dọa nội bộ. Việc
      giám sát tuân thủ Nghị định 13/2023/PDPD và GDPR Art. 88 — chỉ áp dụng cho thiết bị thuộc sở
      hữu công ty, có thông báo rõ ràng và không thu thập nội dung cá nhân ngoài phạm vi bảo mật.
    </span>
  </>
);

const DEFAULT_COMPACT = (
  <>
    <strong>Giám sát hợp pháp:</strong> log hành vi từ máy công ty được thu thập theo Nghị định
    13/2023 và GDPR Art. 88. Chỉ dành cho thiết bị doanh nghiệp.
  </>
);

/**
 * Legal banner shown on the login page and (optionally) on the agent
 * startup. Mirrors the legal notice printed by the agent's CLI banner so
 * the message is consistent across surfaces (PDPD / GDPR compliance).
 */
export function LegalBanner({ children, variant = 'compact', className }: LegalBannerProps) {
  return (
    <aside className={`legal-banner legal-banner--${variant} ${className ?? ''}`.trim()}>
      <ScrollText size={16} />
      <div className="legal-banner-text">{children ?? (variant === 'full' ? DEFAULT_FULL : DEFAULT_COMPACT)}</div>
    </aside>
  );
}

export default LegalBanner;
