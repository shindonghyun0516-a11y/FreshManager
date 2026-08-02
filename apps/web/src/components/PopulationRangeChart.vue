<script setup lang="ts">
import { computed, ref } from "vue";

import { calculatePopulationChange, midpoint } from "../prototype/prototype-calculations";
import type { PopulationRange } from "../prototype/prototype-types";

type ChartSlot = Readonly<{
  id: "current" | "60" | "120" | "180";
  label: string;
  range: PopulationRange | null;
  contractPending?: boolean;
}>;

type PointId = ChartSlot["id"];

const props = withDefaults(defineProps<{
  ariaPrefix: string;
  compact?: boolean;
  slots: readonly ChartSlot[];
  testId: string;
}>(), { compact: false });

const formatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });
const xPositions = [42, 134, 226, 318] as const;
const hoveredPointId = ref<PointId | null>(null);
const focusedPointId = ref<PointId | null>(null);
const selectedPointId = ref<PointId | null>(null);
const activePointId = ref<PointId | null>(null);

const chart = computed(() => {
  const values = props.slots.flatMap((slot) => slot.range ? [slot.range.min, slot.range.max] : []);
  const rawMin = values.length ? Math.min(...values) : 0;
  const rawMax = values.length ? Math.max(...values) : 1;
  const padding = Math.max((rawMax - rawMin) * 0.12, rawMax * 0.03, 1);
  const chartMin = rawMin - padding;
  const chartMax = rawMax + padding;
  const y = (value: number) => 110 - ((value - chartMin) / Math.max(chartMax - chartMin, 1)) * 96;
  const current = props.slots[0]?.range ?? null;
  const points = props.slots.map((slot, index) => {
    const change = current && slot.range && slot.id !== "current"
      ? calculatePopulationChange(current, slot.range)
      : null;
    const pointMidpoint = slot.range ? midpoint(slot.range) : null;
    const tooltipLabel = slot.id === "current" ? "현재" : `${slot.label} 후`;
    const detailLabel = slot.contractPending
      ? "데이터 준비 중"
      : !slot.range
        ? "예상 유동인구 데이터 없음"
        : slot.id === "current"
          ? "변화 계산의 기준 시점"
          : change
            ? `현재 대비 ${formatSigned(change.amount)}명 (${formatRate(change.rate)})`
            : "현재 대비 변화 계산 불가";
    const rangeLabel = slot.range ? `예상 유동인구 ${formatRange(slot.range)}` : "";
    return {
      ...slot,
      change,
      detailLabel,
      midpoint: pointMidpoint,
      rangeLabel,
      tooltipLabel,
      accessibleLabel: [tooltipLabel, rangeLabel, detailLabel].filter(Boolean).join(", "),
      x: xPositions[index],
      yMax: slot.range ? y(slot.range.max) : null,
      yMid: pointMidpoint === null ? null : y(pointMidpoint),
      yMin: slot.range ? y(slot.range.min) : null,
    };
  });
  const segments = points.slice(0, -1).flatMap((point, index) => {
    const next = points[index + 1];
    return point.yMid === null || next.yMid === null
      ? []
      : [{ id: `${point.id}-${next.id}`, x1: point.x, y1: point.yMid, x2: next.x, y2: next.yMid }];
  });
  const ariaLabel = points.map((point) => point.accessibleLabel).join(". ");
  return { ariaLabel: `${props.ariaPrefix}. ${ariaLabel}`, points, segments };
});

const activePoint = computed(
  () => chart.value.points.find((point) => point.id === activePointId.value) ?? null,
);
const activeTooltipId = computed(
  () => activePoint.value ? `${props.testId}-tooltip-${activePoint.value.id}` : null,
);
const tooltipPositionClass = computed(() => {
  const index = chart.value.points.findIndex((point) => point.id === activePointId.value);
  if (index === 0) return "tooltip-start";
  if (index === chart.value.points.length - 1) return "tooltip-end";
  return "tooltip-center";
});

function formatRange(value: PopulationRange | null): string {
  return value ? `${formatter.format(value.min)} ~ ${formatter.format(value.max)}명` : "—";
}

function formatNumber(value: number): string {
  return formatter.format(value);
}

function formatSigned(value: number): string {
  return `${value > 0 ? "+" : ""}${formatter.format(value)}`;
}

function formatRate(value: number | null): string {
  if (value === null) return "증감률 계산 불가";
  return `${value > 0 ? "+" : ""}${formatter.format(value * 100)}%`;
}

function pointStyle(point: { x: number; yMid: number | null }) {
  return {
    left: `${(point.x / 360) * 100}%`,
    top: `${((point.yMid ?? 66) / 124) * 100}%`,
  };
}

function activateHover(pointId: PointId) {
  hoveredPointId.value = pointId;
  activePointId.value = pointId;
}

function deactivateHover(pointId: PointId) {
  if (hoveredPointId.value === pointId) hoveredPointId.value = null;
  if (activePointId.value === pointId) {
    activePointId.value = focusedPointId.value ?? selectedPointId.value;
  }
}

function activateFocus(pointId: PointId) {
  focusedPointId.value = pointId;
  activePointId.value = pointId;
}

function deactivateFocus(pointId: PointId) {
  if (focusedPointId.value === pointId) focusedPointId.value = null;
  if (activePointId.value === pointId) {
    activePointId.value = hoveredPointId.value ?? selectedPointId.value;
  }
}

function selectPoint(pointId: PointId) {
  selectedPointId.value = pointId;
  activePointId.value = pointId;
}

function clearInteraction() {
  hoveredPointId.value = null;
  focusedPointId.value = null;
  selectedPointId.value = null;
  activePointId.value = null;
}
</script>

<template>
  <figure class="forecast-chart" :class="{ 'forecast-chart-compact': compact }" :data-testid="testId" :aria-label="chart.ariaLabel">
    <div class="forecast-chart-stage">
      <svg class="forecast-chart-plot" viewBox="0 0 360 124" aria-hidden="true" focusable="false">
        <line class="forecast-chart-guide" x1="20" y1="14" x2="340" y2="14" />
        <line class="forecast-chart-guide" x1="20" y1="62" x2="340" y2="62" />
        <line class="forecast-chart-axis" x1="20" y1="110" x2="340" y2="110" />
        <line
          v-for="segment in chart.segments"
          :key="segment.id"
          class="forecast-chart-segment"
          :x1="segment.x1"
          :y1="segment.y1"
          :x2="segment.x2"
          :y2="segment.y2"
        />
        <g v-for="point in chart.points" :key="point.id">
          <template v-if="point.range && point.yMax !== null && point.yMid !== null && point.yMin !== null">
            <line class="forecast-chart-range" :class="{ 'is-current': point.id === 'current' }" :x1="point.x" :x2="point.x" :y1="point.yMax" :y2="point.yMin" />
            <line class="forecast-chart-cap" :x1="point.x - 5" :x2="point.x + 5" :y1="point.yMax" :y2="point.yMax" />
            <line class="forecast-chart-cap" :x1="point.x - 5" :x2="point.x + 5" :y1="point.yMin" :y2="point.yMin" />
            <circle
              class="forecast-chart-point"
              :class="{ 'is-current': point.id === 'current', 'is-active': activePointId === point.id }"
              :cx="point.x"
              :cy="point.yMid"
              :r="point.id === 'current' ? 6 : 5"
            />
          </template>
          <text v-else class="forecast-chart-empty" :x="point.x" y="66">—</text>
        </g>
      </svg>

      <div class="forecast-chart-hit-targets">
        <button
          v-for="point in chart.points"
          :key="point.id"
          class="chart-point-trigger"
          :class="{ 'is-active': activePointId === point.id }"
          :style="pointStyle(point)"
          type="button"
          tabindex="0"
          :aria-label="`${point.tooltipLabel} 정보 보기`"
          :aria-describedby="activePointId === point.id && activeTooltipId ? activeTooltipId : undefined"
          @mouseenter="activateHover(point.id)"
          @mouseleave="deactivateHover(point.id)"
          @focus="activateFocus(point.id)"
          @blur="deactivateFocus(point.id)"
          @click="selectPoint(point.id)"
          @keydown.esc.stop="clearInteraction"
        >
          <span class="sr-only">{{ point.tooltipLabel }} 정보 보기</span>
        </button>
      </div>

      <div
        v-if="activePoint && activeTooltipId"
        :id="activeTooltipId"
        class="chart-tooltip"
        :class="tooltipPositionClass"
        role="tooltip"
      >
        <strong>{{ activePoint.tooltipLabel }}</strong>
        <span v-if="activePoint.rangeLabel">{{ activePoint.rangeLabel }}</span>
        <span
          :class="{
            increase: activePoint.change && activePoint.change.amount > 0,
            decrease: activePoint.change && activePoint.change.amount < 0,
          }"
        >
          {{ activePoint.detailLabel }}
        </span>
      </div>
    </div>

    <dl class="forecast-chart-labels">
      <div v-for="point in chart.points" :key="point.id">
        <dt>{{ point.label }}</dt>
        <dd :class="{ 'contract-pending': point.contractPending }">
          <template v-if="point.contractPending">데이터 준비 중</template>
          <template v-else-if="point.range">
            <span class="range-bound">{{ formatNumber(point.range.min) }} ~</span>
            <span class="range-bound">{{ formatNumber(point.range.max) }}명</span>
          </template>
          <template v-else>—</template>
        </dd>
      </div>
    </dl>
    <figcaption class="forecast-chart-caption">세로선은 최소~최대 예상 범위이며, 점을 선택하면 현재 대비 변화를 확인할 수 있습니다.</figcaption>
  </figure>
</template>
