import type { PopulationRange } from "./prototype-types";

export function midpoint(range: PopulationRange): number {
  return (range.min + range.max) / 2;
}

export function calculatePopulationChange(current: PopulationRange, forecast: PopulationRange): Readonly<{ amount: number; rate: number | null }> {
  const currentMidpoint = midpoint(current);
  const amount = midpoint(forecast) - currentMidpoint;
  return { amount, rate: currentMidpoint === 0 ? null : amount / currentMidpoint };
}
