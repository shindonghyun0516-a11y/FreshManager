<script setup lang="ts">
const areaState = "AREA_UNSELECTED" as const;
const mapState = "MAP_PLACEHOLDER" as const;
</script>

<template>
  <div class="app-shell" :data-area-state="areaState">
    <header class="app-header">
      <div>
        <p class="eyebrow">Area-first 판매 준비</p>
        <h1>FreshManager</h1>
      </div>
      <button
        class="icon-button"
        type="button"
        aria-label="도움말은 후속 UI 연결 단계에서 제공됩니다."
        disabled
      >
        ?
      </button>
    </header>

    <main class="app-main">
      <section class="control-bar" aria-labelledby="area-selection-title">
        <div class="field">
          <label id="area-selection-title" for="area-select">담당 구역</label>
          <select id="area-select" aria-describedby="area-select-help" disabled>
            <option>담당 Area를 선택하세요</option>
          </select>
          <span id="area-select-help" class="field-help">
            승인 구역 목록은 Read-only API 구현 단계에서 연결됩니다.
          </span>
        </div>

        <p class="data-time">
          <span>데이터 기준시각</span>
          <strong>—</strong>
        </p>
      </section>

      <section
        class="map-shell"
        :data-map-state="mapState"
        aria-labelledby="map-title"
      >
        <div
          class="map-placeholder"
          role="img"
          aria-label="실제 지도와 위치 데이터가 연결되지 않은 지도 자리"
        >
          <span class="status-badge">지도 준비 화면</span>
          <h2 id="map-title">담당 Area를 선택하세요</h2>
          <p>
            지도의 실제 위치와 후보 지점은 NAVER Maps 통합 단계에서 연결됩니다.
          </p>
        </div>

        <nav class="map-actions" aria-label="지도 정보 열기">
          <button type="button" disabled>구역 정보</button>
          <button type="button" disabled>후보 위치 3곳</button>
          <button type="button" disabled>내 위치 표시</button>
        </nav>

        <aside
          class="desktop-drawer"
          data-state="closed"
          aria-label="닫힌 데스크톱 정보 서랍"
          aria-hidden="true"
          hidden
        >
          <h2>구역 정보</h2>
        </aside>
        <section
          class="mobile-bottom-sheet"
          data-state="closed"
          aria-label="닫힌 모바일 정보 시트"
          aria-hidden="true"
          hidden
        >
          <h2>선택 정보</h2>
        </section>
      </section>
    </main>

    <footer class="app-footer">
      실제 Area·Spot 데이터, 지도, 위치 기능과 배포는 아직 연결되지 않았습니다.
    </footer>
  </div>
</template>
