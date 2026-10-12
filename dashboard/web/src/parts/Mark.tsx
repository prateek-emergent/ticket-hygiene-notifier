/** The mark: one light with its trail, the product's whole idea at 32px. */
export function Mark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="mark-trail" x1="0" x2="1">
          <stop offset="0" stopColor="var(--alert)" stopOpacity="0" />
          <stop offset="1" stopColor="var(--alert)" />
        </linearGradient>
        <radialGradient id="mark-light">
          <stop offset="0" stopColor="var(--clean)" />
          <stop offset=".55" stopColor="var(--ok)" />
          <stop offset="1" stopColor="var(--ok)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect x="3" y="18" width="18" height="3" rx="1.5" fill="url(#mark-trail)" />
      <circle cx="21" cy="13" r="7" fill="url(#mark-light)" />
    </svg>
  );
}
