import type { EvidenceStrength } from "../types";

export function EvidenceStrengthBadge({ strength }: { strength: EvidenceStrength }) {
  return <span className={`badge ${strength}`}>evidence {strength}</span>;
}
