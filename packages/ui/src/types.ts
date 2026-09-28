// Structural prop types for @nf/ui. Kept independent of @nf/content so components stay reusable;
// apps/web maps content onto these shapes.
export type Status = 'designed' | 'planned' | 'roadmap' | 'in-preparation';
export interface UiLink {
  label: string;
  href: string;
  status?: Status;
}
export interface UiCta {
  label: string;
  href: string;
  variant: 'primary' | 'ghost';
  disabled?: boolean;
  note?: string;
}
export type StatusLabels = Record<Status, string>;
