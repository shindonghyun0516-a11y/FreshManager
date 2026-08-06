<script setup lang="ts">
import { computed } from "vue";

import { midpoint } from "../prototype/prototype-calculations";
import type { AnalysisFixture, RepeatedPeakFixture, TimeBucketFixture } from "../prototype/prototype-types";

const props = defineProps<{
  analysis: AnalysisFixture;
  buckets: readonly TimeBucketFixture[];
  peaks: readonly RepeatedPeakFixture[];
}>();

const formatter = new Intl.NumberFormat("ko-KR");
const bars = computed(() => {
  const values = props.buckets.map((bucket) => midpoint({ min: bucket.population_min, max: bucket.population_max }));
  const max = Math.max(...values, 1);
  return props.buckets.map((bucket, index) => ({
    ...bucket,
    height: `${Math.max(16, (values[index] / max) * 100)}%`,
    midpoint: values[index],
  }));
});
const ariaLabel = computed(() => bars.value.map((bucket) =>
  `${bucket.time_label} 평균 유동인구 ${formatRange(bucket.population_min, bucket.population_max)}`,
).join(". "));
const orderedPeaks = computed(() => [...props.peaks].sort(
  (left, right) => right.occurrence_count - left.occurrence_count || left.start_time.localeCompare(right.start_time),
));

function formatRange(min: number, max: number): string {
  return `${formatter.format(min)}~${formatter.format(max)}명`;
}

function peakLabel(index: number): string {
  return index === 0 ? "가장 자주 붐빈 시간" : "다음으로 자주 붐빈 시간";
}
</script>

<template>
  <figure class="pattern-chart" data-testid="area-pattern-chart">
    <div class="pattern-bars" role="img" :aria-label="ariaLabel">
      <i v-for="bucket in bars" :key="bucket.time_label" :style="{ height: bucket.height }"></i>
    </div>
    <dl class="pattern-bucket-labels">
      <div v-for="bucket in bars" :key="bucket.time_label">
        <dt>{{ bucket.time_label }}</dt>
        <dd>{{ formatRange(bucket.population_min, bucket.population_max) }}</dd>
        <dd class="pattern-average-label">평균 유동인구</dd>
      </div>
    </dl>
    <figcaption class="forecast-chart-caption">
      {{ analysis.analysis_basis_label }} · 시간대당 {{ analysis.observations_per_time_bucket }}개 관측
    </figcaption>
  </figure>
  <h5 class="peak-list-title">자주 붐비는 시간</h5>
  <dl class="peak-list" aria-label="자주 붐비는 시간">
    <div
      v-for="(peak, index) in orderedPeaks"
      :key="`${peak.start_time}-${peak.end_time}`"
      :aria-label="`${peakLabel(index)}, ${peak.start_time}부터 ${peak.end_time}, ${analysis.analysis_period_label} 중 ${peak.occurrence_count}회`"
    >
      <dt>{{ peakLabel(index) }}</dt>
      <dd>
        <span>{{ peak.start_time }}~{{ peak.end_time }}</span>
        <span>{{ analysis.analysis_period_label }} 중 {{ peak.occurrence_count }}회</span>
      </dd>
    </div>
  </dl>
</template>
