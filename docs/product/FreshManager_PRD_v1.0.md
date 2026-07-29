**PRODUCT REQUIREMENTS DOCUMENT**

# FreshManager 제품 요구사항 정의서

> 프레시매니저 유동판매 위치·시간 추천 서비스 — 공개데이터 기반 데이터 타당성 PoC

**문서 ID:** FM-PRD-001

**버전 / 상태:** v1.1 · 공식 제품 기준

**기준일:** 2026-07-24 (Asia/Seoul)

**제품 책임자:** PM/PO 신동현

**기술 기준:** 구현 계약은 `docs/engineering/FreshManager_TRD_v1.0.md`, 현재
Branch·Pull Request·Issue·실행 상태는 `PROJECT_STATUS.md`를 단일 기준으로 사용

**2026-07-24 변경이력:** EG-8을 상위 Gate로 유지하고 EG-8A~EG-8E로 세분화했다.
PoC 범위에 미래 Area 인구·피크 예측, Area/Spot Ranking, Recommendation Output
Contract, UI/UX 설계·와이어프레임·프로토타입을 포함했다. 상세는 §39 변경 이력을
따른다. **문서 내용 버전은 v1.1**이며, **정본 파일 경로는 기존 링크와
Project Guard 자동검사 호환성을 위해 그대로 유지**한다. 파일명의 `_v1.0`은
현재 내부 문서 버전을 의미하지 않는 **Legacy Stable Path**다.

**2026-07-22 변경이력:** Issue #58 초안에서 Google Drive 자동 백업,
첫 Batch 이후 CSV와 Area·선택적 S-DoT·Spot Candidate Evaluation·Recommendation
Workstream 결정을 반영했다.

> **핵심 결론**  현재 제품은 추천 앱이 아니라, 추천 서비스가 성립할 데이터
> 전제조건을 검증하는 1인 운영 PoC다. 장기 후보군은 서울시 121개 Area지만 승인
> MVP 공간 범위는 13개 Area 패널이다. 구현·실행 완료 여부와 다음 작업은
> `PROJECT_STATUS.md`에서 확인한다.

## 문서 구성

이 문서는 아래 순서로 읽도록 구성했다. PM은 1~4장을 먼저 보고, 구현·검증 담당자는 요구사항과 추적성 장을 이어서 확인한다.

- 1~4장: 제품 비전, 문제, 사용자, 목표와 경계
- 5~8장: 공간·데이터 범위, 가설, 사용자 시나리오, 기능 요구사항
- 9~12장: 비기능 요구사항, 성공 판정, 실험·로드맵, 운영 승인
- 13~16장: 리스크, 의존성, 의사결정, 수용·추적성

## 1. 제품 정의와 문서 목적

FreshManager의 장기 비전은 프레시매니저가 정기배송 이후 유동판매를 수행할 때, 이동 가능한 장소와 시간을 데이터로 보조하는 서비스다. 그러나 현재 릴리즈의 제품은 모바일 앱이나 추천 화면이 아니라 서울시 공개데이터가 그 의사결정을 뒷받침할 수 있는지를 검증하는 데이터 타당성 PoC다.

이 PRD는 기존 요구사항 정의서 v0.4, 병합된 구현 계약, EG-5 실제 수집 분석과
EG-6A 패널을 하나의 제품 기준으로 정리한다. 제품이 무엇을 해결해야 하는지,
무엇을 아직 주장할 수 없는지, 어떤 결과를 성공으로 볼지를 정의하며 구현 세부는
별도 TRD에, 현재 진행 상태는 `PROJECT_STATUS.md`에 위임한다.

> **범위 경계**  본 PoC가 낼 수 있는 결론은 ‘공개데이터가 유동판매 후보 탐색에 쓸 수 있는가’까지다. ‘이 장소·시간에 야쿠르트가 더 잘 팔린다’는 결론은 실제 판매·현장 결과 없이 내릴 수 없다.

## 2. 배경과 문제 정의

### 2.1 장기 문제 가설

프레시매니저가 유동판매 위치와 시간을 개인 경험에 크게 의존해 추가 판매 기회를 놓칠 수 있다는 것이 장기 문제 가설이다. 현재까지 이 가설은 인터뷰나 hy 내부 판매데이터로 검증된 사실이 아니다. 따라서 PoC는 문제 자체를 확정하지 않고, 그보다 앞선 데이터 전제조건을 검증한다.

### 2.2 현재 검증 문제

- 서울시 공식 Area 단위의 현재 인구·혼잡과 12시간 예측을 안정적으로 반복 수집할 수 있는가?
- 같은 미래시점에 대한 여러 예측 스냅샷을 보존하고 후속 관측값과 비교할 수 있는가?
- 요일·시간대·장소 유형별로 반복되는 패턴과 비관행 피크가 존재하는가?
- 인구 변화와 카드소비 기반 소비활동 대리변수가 함께 움직이는가?
- 예측 리드타임이 실제 이동·판매 준비에 활용 가능한 수준인가?
- Area 단위 신호가 Spot 후보와 연결될 때 과대해석 없이 의사결정 근거가 될 수 있는가?

### 2.3 현재까지 확인된 증거

EG-4에서 여의도 POI072 실제 응답과 원본·메타데이터 저장을 확인했고, EG-5에서 구로디지털단지역·가산디지털단지역·강남역을 각각 1회 수집해 모두 성공했다. EG-5 단면 분석은 세 장소의 인구 규모, 혼잡 지속성, 비상주 비율과 예측 경로가 구분됨을 확인했다.

| **장소** | **현재 인구 중심값** | **현재 혼잡** | **핵심 관찰** |
| --- | --- | --- | --- |
| 구로디지털단지역 | 35,000 | 보통 | 20~50대 88.4%, 19시 이후 예측 감소 |
| 가산디지털단지역 | 37,000 | 약간 붐빔 | 비상주 67.4%, 17시 예측 최고 |
| 강남역 | 95,000 | 붐빔 | 절대 인구·혼잡 지속성 최대 |

*이 결과는 Feature 구조와 장소 간 분별력을 지지하지만, 반복 패턴·예측 성능·판매효과는 아직 평가할 수 없다.*

## 3. 대상 사용자와 이해관계자

| **대상** | **현재 역할** | **핵심 요구** | **결정 권한** |
| --- | --- | --- | --- |
| PM/PO 신동현 | PoC 운영자·최종 승인자 | 비개발자도 실행·판정 가능한 증거 | 범위, 실제 호출, 다음 Gate, Merge |
| 분석 담당자 | 현재 시스템의 직접 사용자 | 재현 가능한 수집·품질·분석 데이터 | 분석 실행·리포트 작성 |
| 프레시매니저 | 장기 목표 사용자 | 이동 가능한 후보 시간·장소와 이유 | 후속 화면 기반 사용성 검토 |
| hy 이해관계자 | 후속 제휴·실증 검토자 | 과대해석 없는 정량 근거와 한계 | 내부 데이터·운영 실증 승인 |
| Codex/개발 지원 | 구현·검증·문서화 보조 | 명확한 계약·승인 경계·자동검사 | 독자 승인권 없음 |

## 4. 제품 원칙

**증거 우선:** 확인된 사실, 해석, 가설을 분리하고 단일 시점 결과를 반복 패턴이나 인과로 일반화하지 않는다.

**유동인구 ≠ 매출:** 인구·혼잡은 기회와 운영 난이도의 대리신호이며, 카드소비는 일반 소비활동 대리변수다.

**Area ≠ Spot:** 서울시 Area 수집값을 특정 출구·건물 앞 보행량으로 표현하지 않는다.
Spot은 고정 판매 위치가 아니라 Area·S-DoT·공간 Context와 원격 근거를 바탕으로
구성하는 판매 후보 위치다. 현재 PoC에서는 현장검증을 할 수 없으며 최대 출력은
데이터 기반 우선 후보다.

**시점 무결성:** 요청·관측·예측 스냅샷·예측 대상·후속 관측 시각을 분리하고 미래정보 누수를 금지한다.

**원본 불변:** 모든 응답 원본과 예측 스냅샷은 덮어쓰지 않고 요청 단위로 보존한다.

**Human-in-the-loop:** 실제 API 호출, 주기, 저장구조, 다음 Gate와 Merge는 PM 명시 승인 후 진행한다.

**1인 운영 적합성:** 표준 라이브러리와 최소 구성으로 시작하고 실제 필요가 확인된 복잡성만 추가한다.

**로컬 원본 우선:** 로컬 Raw·Metadata·Collection Log·Manifest가 공식 원본이다.
Google Drive에는 검증된 복사본을 자동 백업하며 백업 실패는 API 재호출 사유가 아니다.

**결과 수준:** 원격 근거가 충분한 Spot은 `recommendation_scope=DATA_PRIORITY_ONLY`인
데이터 기반 우선 후보로만 기록한다. 근거가 부족하면 판매 후보 또는 AREA 안내로
하향한다. 현재 `STATION_CENTER_PROXY`는 실제 Spot이나 검증된 판매 위치가 아니다.
`operational_suitability_status=NOT_VERIFIED`를 유지하며 공식 Recommendation
Output의 `target_level=SPOT`으로 자동 승격하지 않는다.

## 5. 목표와 비목표

### 5.1 제품 목표

- G1. 승인된 공식 Area를 안정적으로 수집하고 장소별 실패가 전체 회차를 파괴하지 않도록 한다.
- G2. 원본·메타데이터·예측 스냅샷·회차 증거를 재현 가능하게 보존한다.
- G3. 시간대·요일·장소별 반복성과 예측-후속관측 일치도를 평가할 데이터 기반을 만든다.
- G4. 인구 기회와 혼잡 위험을 분리하고, 카드소비·날씨·S-DoT를 과대해석 없이 보조한다.
- G5. Gate A·B 판정과 Gate C 인터뷰로 넘어갈지 결정할 수 있는 정량 리포트를 만든다.
- G6. 비개발자 PM이 실행 결과, 실패 이유, 다음 승인사항을 이해할 수 있게 한다.

### 5.2 현재 PoC 범위에 포함하는 항목 (EG-8A~EG-8E)

- 미래 Area 인구 예측, 피크 발생 여부와 예상 피크시각(EG-8C)
- Area Ranking, Spot Candidate Ranking, 지원·접근·수집·품질조건을 만족하는
  선택적 S-DoT 보조정보(EG-8D)
- Recommendation Output Contract 설계(EG-8E) — 점수·가중치·임계값의 최종 확정은
  포함하지 않는다(D-009 `OPEN_DECISION` 유지)
- UI/UX 정보구조·와이어프레임·프로토타입(비상용 설계 산출물, EG-8E)

상세 진입·통과조건은 `docs/testing/QUALITY_GATES.md`가 소유한다.

### 5.3 데이터 수집에서 이동 판단 지원까지의 사용자 가치 흐름

```text
승인 13개 Area 5분 자동수집(Apps Script Runtime, ACTIVE)
→ EG-8A Python Loader·정규화·데이터 품질
→ EG-8B EDA·서울시 Forecast 평가·Baseline·Feature Dataset
→ EG-8C 미래 Area 인구·피크 예측 모델
→ EG-8D Area Ranking·선택적 S-DoT·Spot Candidate Evaluation
→ EG-8E Recommendation Output Contract·UI/UX Readiness
→ (별도 PM 승인 후) UI/UX 상세 설계·프로토타입
→ (Recommendation MVP Workstream, Gate number `NOT_ASSIGNED`) 이동 판단 지원
```

이 흐름은 목표 설계이며 각 단계는 이전 단계 통과와 별도 PM 승인 후 진행한다.
UI는 Model Output을 직접 소비하지 않고 Recommendation Output만 소비한다.
실제 판매효과·구매전환은 이 흐름만으로 입증되지 않는다.

### 5.4 현재 명시적 비목표

- 판매량 예측, 매출 예측, 판매 성공확률, 제품별 수요예측, 재고 최적화
- 판매성과 인과효과 검증
- 상용 모바일 앱·웹 서비스 구현 및 출시, 상용 지도 서비스 개발·배포, 알림 UX 확정
- 실시간 모델 서빙, 완성형 MLOps
- 프레시매니저 위치 추적, 고객 개인정보 수집 또는 개인별 프로파일링
- 실제 판매량 수집·구매전환율 검증
- 개별 건물·출구·흡연부스·오피스 입구 단위 정밀 Spot 추천과 이동경로 최적화
- 현재 Candidate Anchor의 실제 출구 해석, 공식 Spot 추천 제공 또는 출구 단위
  추천 정확도 검증 주장
- 상품 추천과 예상매출 제공
- 추천 점수 모델·가중치·임계값의 최종 확정(D-009 `OPEN_DECISION` 유지)
- hy 내부 데이터, 유료 데이터 또는 프로덕션 대규모 인프라 연동
- 호출한도 확인 전 121개 Area 고빈도 자동수집
- 별도 PM Live 승인 없는 실제 5분 반복수집·자동 재시도·클라우드 실행

이 현재 PoC 비목표는 장기 제품 목표에서의 영구 제외를 뜻하지 않는다. 실제 Spot
좌표와 Area 내부 복수 후보, Spot별 동적·정적 근거, 반복성·Backtesting과 원격
운영제한 자료가 확보되면 데이터 기반 우선 후보까지 검토할 수 있다. 실제 안전·
카트 정차·판매 허용과 운영 적합성은 별도 운영기관 확인 없이는 확정하지 않는다.

## 6. 범위 모델

### 6.1 단계별 공간 범위

> **공식 범위**  장기 후보군은 서울시 121개 Area다. 현재 MVP 수집·분석 패널은 EG-6A에서 확정한 13개 Area·Spot·S-DoT 연결이다. 121개 확대는 EG-7 반복수집, EG-8(상위, EG-8A~8E)과 별도 승인된 Recommendation MVP Workstream의 데이터 필요성을 확인한 뒤에만 검토한다.

| **계층** | **정의** | **현재 사용** | **금지되는 해석** |
| --- | --- | --- | --- |
| Area | 서울시 API의 공식 공간 단위 | 13개 승인 패널 | 특정 출구·건물 앞 직접 인구 |
| Spot Candidate | Area·S-DoT·공간 Context 기반 판매 후보 위치 | 역 중심 Candidate Anchor 13개 | 검증된 고정 판매지점 |
| S-DoT Link | Area 내부 활성 위치 판단을 위한 센서 보조 연결 | 직접 3·인근 4·미지원 6 | Area 대체값·판매량·추천 적중 결과 |

### 6.2 공식 서비스 데이터 구조

| **구조** | **목적** | **핵심 데이터·책임** |
| --- | --- | --- |
| Core Observation | 판매 가능 Area 탐색 | 모든 승인 Area에서 확보하는 인구 범위·혼잡도·Forecast·시간대 변화 |
| Optional Supporting Observation | Area 내부 활성 위치 판단 보조 | 지원·접근·수집·품질조건을 만족할 때만 쓰는 S-DoT 위치·관측; Area Collector와 독립 |
| Additional Context | 후보의 공간·운영 타당성 보강 | Spatial Context·Field Validation·Operational Constraints |
| Spot Candidate Evaluation | Area 내부 판매 후보 위치 평가 | Area Feature + 선택적 S-DoT Feature + Additional Context의 Candidate Evidence Assessment |
| Recommendation 결과 | 추천 단위 결정 | 신뢰 가능한 Spot은 `SPOT`, 없으면 `AREA`와 `fallback_reason` |

EG-6B는 필수 Area Observation을 확보한다. 정적 EG-6A 참조 연결은 실행 전 무결성
입력이지만, 동적 S-DoT 관측 수집과 Spot Candidate Evaluation은 후속 독립 책임이므로
EG-6B Collector의 요청 책임에 포함하지 않는다. S-DoT 미지원 6개 Area도 Area 분석과
추천 후보에서 제외하지 않는다. Score·가중치·임계값은 `PLANNED` 또는
`OPEN_DECISION`이다.

### 6.3 승인된 13개 Area 패널

| **#** | **서비스 지역** | **코드** | **공식 Area** | **매핑** | **S-DoT** |
| --- | --- | --- | --- | --- | --- |
| 1 | 구로디지털단지역 | POI019 | 구로디지털단지역 | 정확 | 미지원 |
| 2 | 가산디지털단지역 | POI013 | 가산디지털단지역 | 정확 | 미지원 |
| 3 | 강남역 | POI014 | 강남역 | 정확 | 직접 |
| 4 | 여의도역 | POI072 | 여의도 | 관련 | 미지원 |
| 5 | 삼성역 | POI001 | 강남 MICE 관광특구 | 관련 | 미지원 |
| 6 | 선릉역 | POI034 | 선릉역 | 정확 | 인근 |
| 7 | 역삼역 | POI042 | 역삼역 | 정확 | 미지원 |
| 8 | 뚝섬역 | POI025 | 뚝섬역 | 정확 | 직접 |
| 9 | 광화문역 | POI088 | 광화문광장 | 관련 | 인근 |
| 10 | 을지로입구역 | POI003 | 명동 관광특구 | 관련 | 인근 |
| 11 | 잠실역 | POI119 | 잠실역 | 정확 | 인근 |
| 12 | 서울역 | POI033 | 서울역 | 정확 | 미지원 |
| 13 | 마곡나루역 | POI032 | 서울식물원·마곡나루역 | 관련 | 직접 |

*현재 Spot Master의 모든 행은 STATION_CENTER_PROXY·field_verified=false인 Candidate
Anchor Point다. 실제 판매 Spot 확정 데이터가 아니며, 판교역은 서울시 범위 밖이므로
뚝섬역으로 대체됐다.*

## 7. 제품 가설

| **ID** | **가설** | **검증 명제** | **검증 단계** |
| --- | --- | --- | --- |
| H1 | 시간패턴 반복성 | 동일 Area·요일·시간의 인구·혼잡 패턴이 여러 주 반복된다. | EG-7/8 |
| H2 | 공식 예측 유용성 | 서울시 예측이 단순 기준선보다 후속 관측에 더 가깝다. | EG-7/8 |
| H3 | 장소 유형 차이 | 오피스·환승·관광·공원형 Area의 시간경로가 구분된다. | EG-8 |
| H4 | 비관행 피크 | 출퇴근·점심 외에도 반복적이고 이동 가능한 피크가 존재한다. | EG-8 |
| H5 | 인구·소비 동행 | 인구 변화와 카드소비 기반 소비활동 단계가 일부 시간대에 동행한다. | 후속 연동 |
| H6 | 날씨 영향 | 예측 시점에 알 수 있던 날씨 예보가 패턴 차이를 설명한다. | 후속 연동 |

## 8. 사용자 시나리오와 기능 요구사항

### 8.1 핵심 사용자 시나리오

- US-01 분석 담당자는 승인된 13개 Area를 한 회차로 수집하고 성공·실패·소요시간을 확인한다.
- US-02 분석 담당자는 같은 미래시점의 여러 예측 스냅샷과 후속 관측을 연결해 리드타임별 오차를 계산한다.
- US-03 PM은 일반 테스트가 실제 API를 호출하지 않았음을 확인하고, 실제 호출·주기·다음 Gate를 별도로 승인한다.
- US-04 분석 담당자는 출퇴근·점심 외 반복 피크와 장소 간 상대순위 안정성을 탐색한다.
- US-05 PM은 인구 기회, 혼잡 위험, 소비활동 대리변수와 데이터 한계를 함께 본다.
- US-06 장기적으로 프레시매니저는 담당구역·재고·이동시간을 고려한 후보를 확인하지만, 이 기능은 현 PoC 범위 밖이다.

### 8.2 요구사항 요약

| **ID** | **우선** | **요구사항** | **현재** |
| --- | --- | --- | --- |
| FR-01 | P0 | 공식 기준·패널 검증 | 구현 |
| FR-02 | P0 | 승인형 단일·배치 실행 | 구현 |
| FR-03 | P0 | 원본·8필드 메타데이터 보존 | 구현 |
| FR-04 | P0 | 회차 로그·Manifest·해시 | 구현 |
| FR-05 | P0 | 예측 스냅샷·후속관측 영속화 | 부분 |
| FR-06 | P0 | 데이터 품질 모니터링 | 부분 |
| FR-07 | P1 | 날씨 예보·관측 분리 | 계획 |
| FR-08 | P1 | 카드소비 대리변수 연결 | 계획 |
| FR-09 | P0 | 기준선·피크·예측 평가 | 계획 |
| FR-10 | P0 | 리포트·판정·한계 표시 | 부분 |
| FR-11 | P0 | 실패 격리·종료코드 | 구현 |
| FR-12 | P0 | PM 승인·범위 통제 | 구현 |
| FR-13 | P0 | Google Drive 자동 백업·복구 | 계획 |
| FR-14 | P0 | SPOT 필수·AREA fallback | 계획 |

### 8.3 FR-01 공식 기준·패널 검증

시스템은 data/reference/seoul_121_places.csv를 장소코드의 유일한 기준으로 사용하고, 121행·정확한 헤더·중복 없음·POI072=여의도를 읽기 전용으로 검증해야 한다. EG-6B에서는 eg6_area_panel.csv, eg6_spot_master.csv, eg6_sdot_links.csv의 정확한 헤더·13개 연결·승인·활성 상태와 SHA-256 불변성을 수집 전후 확인해야 한다.

- 검증 실패 시 네트워크 호출 0회와 공통 오류 종료를 보장한다.
- 임의 코드 생성·보정·정렬·재인코딩을 금지한다.
- 패널 순서는 1~13으로 고정하고 중복·누락을 허용하지 않는다.

### 8.4 FR-02 승인형 단일·배치 실행

실제 실행은 명시적 env-file, 저장소 밖 output-root와 --execute-live가 모두 제공된 경우에만 가능해야 한다. 이 옵션은 PM의 외부 실행 승인을 대체하지 않는다.

- 현재 EG-6B 회차는 13개 Area를 각각 최대 1회 호출한다.
- 자동 재시도와 반복 실행은 0회다.
- 실제 13개 호출은 아직 승인·실행되지 않았다.

### 8.5 FR-03 원본·메타데이터 보존

응답 bytes는 변경하지 않은 새 JSON 파일로 저장하고 기존 파일을 덮어쓰지 않아야 한다. 각 요청은 request_id, area_code, endpoint_name, requested_at, received_at, http_status, collection_status, raw_file_path의 정확한 8필드 메타데이터를 가져야 한다.

- 응답을 받은 파싱·검증 오류도 원본을 보존한다.
- endpoint_name은 논리명이며 인증 URL을 저장하지 않는다.
- 결측을 0으로 보정하거나 원본 필드명을 바꾸지 않는다.

### 8.6 FR-04 회차 증거와 무결성

각 EG-6B 회차는 batch_id, 버전, 시작·종료·소요시간, 시도·성공·실패 수, 실패 목록, 재시도 수, 파일 수, 종료코드와 Area별 결과를 collection_log.json에 기록해야 한다. manifest.json은 공식 참조파일과 생성 산출물의 상대경로·크기·SHA-256을 기록하고 저장 후 검증해야 한다.

- 대상 수=성공 수+실패 수가 항상 성립해야 한다.
- 모든 성공은 raw와 metadata 연결을 가져야 한다.
- Manifest 경로는 허용 root 밖으로 탈출할 수 없어야 한다.

### 8.7 FR-05 예측 스냅샷·후속관측 영속화

같은 forecast_target_time의 예측을 수집시점별로 모두 보존해야 하며 requested_at, forecast_snapshot_time, forecast_target_time, followup_observation_time을 구분해야 한다. 현재 파서는 예측을 검증·정규화해 메모리로 반환하지만 분석용 영속 테이블은 아직 구현되지 않았다.

- 예측 키는 area_code + forecast_snapshot_time + forecast_target_time + request_id다.
- 공식 발행시각 필드가 없으면 requested_at을 발행시각으로 이름 바꾸지 않는다.
- 1·3·6시간 리드타임별 평가가 가능해야 한다.

### 8.8 FR-06 데이터 품질 모니터링

회차·Area 단위로 성공률, 결측, 연속 실패, 중복, 관측 지연, 예측 배열 개수·간격, 스키마 변화, 파일 무결성을 측정해야 한다. 현 구현은 입력·응답 구조와 배치 무결성을 엄격히 검사하지만 장기 추세 모니터링은 EG-7에서 추가한다.

- not_supported, missing, 실제 0을 구분한다.
- 32분 지연은 과거 여의도 관측의 기준선이며 모든 Area의 불변 규칙으로 단정하지 않는다.
- 품질 임계치는 실제 반복수집 결과 후 PM이 승인한다.

### 8.9 FR-07 날씨 예보·관측 분리

날씨 예보와 실제 관측을 별도 데이터셋으로 저장하고, 예보의 스냅샷·대상시각을 보존해야 한다. 예측 평가에는 당시 이용 가능했던 예보만 사용하며 후속 실제 날씨를 과거 입력으로 소급하지 않는다.

- 예보 결측을 실제 관측으로 대체하지 않는다.
- 현재 구현·Project Guard에서는 아직 계획 상태다.
- 날씨는 예측 설명력 보조이며 데이터 가설 실패와 분리한다.

### 8.10 FR-08 카드소비 대리변수 연결

지원되는 Area의 상권 활동단계와 기준시각을 인구 데이터와 연결하고 시간차를 기록해야 한다. 결과는 카드소비 기반 소비활동 대리변수로만 표현한다.

- 실제 hy 매출·판매실적·구매전환율로 표현하지 않는다.
- 미지원은 not_supported, 일시 결측은 missing으로 구분한다.
- 지원 범위·실응답 필드 확인 후 구현한다.

### 8.11 FR-09 분석·평가

동일 요일·시간 기준선, 최근값 유지, 최근 4주 평균과 서울시 예측을 비교하고 MAE, RMSE, 상대오차, 예측범위 포함률, 혼잡도 일치율과 리드타임별 오차를 계산해야 한다. 시간대 피크·변화율·변동성·지속시간과 장소 간 순위 안정성도 분석한다.

- 최소 4주 기준선을 구축하고 5주차를 전향 평가한다.
- 1주 데이터로 최종 결론을 내리지 않는다.
- 5주 종료 시 표본 부족이 확인될 때만 1주 연장을 검토한다.

### 8.12 FR-10 리포트·판정

리포트는 확인된 사실, 해석, 가설, 한계를 분리하고 Gate A·B와 Engineering Gate를 혼용하지 않아야 한다. 장소·시간별 차트와 품질표, 예측 비교, 피크·소비·날씨 보조분석, PM 결정사항을 포함한다.

- 판매결과가 없으면 추천 성능을 확정하지 않는다.
- 지원하지 않는 데이터는 조용히 0으로 표시하지 않는다.
- 출처와 공공누리 제1유형 표시 기준을 확인한다.

### 8.13 FR-11 실패 격리·종료코드

Area 단위 api_error, timeout, parse_error, validation_error는 해당 결과를 기록하고 다음 Area를 계속 처리해야 한다. 설정·저장·보안·내부·참조 무결성 등 공통 오류는 안전하게 중단해야 한다.

- EG-6B 종료코드는 전체 성공 0, Area 실패 존재 1, 공통 오류 2다.
- 실패 Area는 재호출하지 않으며 retry_count=0이다.
- 미시도 Area는 not_attempted로 회차 결과에 남긴다.

### 8.14 FR-12 PM 승인·범위 통제

실제 API 호출, 다음 Engineering Gate, 신규 라이브러리, 기준파일·저장구조·확정된
5분 호출주기의 변경·자동실행 변경과 main 병합은 PM 명시 승인 후 진행해야 한다.

- 일반 테스트·Project Guard는 네트워크 호출 0회다.
- 5분은 `PM_APPROVED_FIXED` 장기 기준이며 런타임 선택값이 아니다. 변경에는 새 PM
  명시 결정과 버전 계약·코드 변경 검토가 필요하다.
- 승인 없이 121개 확대나 실제 Live 운영을 확정하지 않는다.
- 결정 필요사항은 대안·장단점·권장안·승인 이유로 보고한다.

### 8.15 FR-13 Google Drive 자동 백업·복구

완료된 Batch의 로컬 공식 원본을 Google Drive for Desktop Sync의 로컬 동기화
폴더에 Batch 완료 직후 자동 백업해야 한다. Collector와 Backup Worker를 분리하고,
완료 판정 후 1회 실행형 Worker를 즉시 호출하는 구조를 사용한다.

- 공식 제공자는 Google Drive이며 iCloud와 수동 백업은 현행 운영방식이 아니다.
- Backup Root는 `FreshManager-Data/` 논리 구조만 정의한다.
- 실제 계정 이메일과 동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- Google Drive API·OAuth·SDK는 구현하지 않는다.
- 완료·부분 실패 Batch는 Manifest 파일 수·SHA-256 검증 후 함께 복사한다.
- 실행 중 Batch, `.env`, Secret, 인증 URL과 임시 파일은 복사하지 않는다.
- 로컬 동기화 폴더 복사와 실제 원격 업로드 완료를 별도 상태로 관리한다.
- 백업 실패·충돌로 서울시 API를 재호출하거나 기존 원본·복사본을 덮어쓰지 않는다.

상세 상태·충돌·Receipt·복원 목표 계약은
`docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`가 소유한다.

### 8.16 FR-14 Spot Candidate·SPOT 우선·AREA fallback

Spot Candidate는 Area 데이터, 선택적 S-DoT 또는 대체 동적 근거와 공식 위치·시설
Context로 구성한다. 원격 근거가 충분하면 데이터 기반 우선 후보로 기록하고,
근거가 부족하면 판매 후보 또는 AREA로 하향해 이유를 기록한다.

- `recommendation_scope=DATA_PRIORITY_ONLY`: 원격 근거 비교의 우선 후보이며 공식 추천 아님
- `target_level=AREA`: 데이터 기반 우선 후보 조건이 충족되지 않음
- `field_verification_status=UNAVAILABLE`: 현재 PoC의 현장검증 불가
- `operational_suitability_status=NOT_VERIFIED`: 판매·안전·정차·운영 적합성 미확인
- AREA fallback에는 `fallback_reason`이 필수다.
- Area Observation은 특정 출구나 Spot의 직접 유동인구가 아니다.
- 동적 S-DoT 관측과 Spot Candidate Evaluation 오류가 EG-6B Area 수집을 중단시키면 안 된다.
- EG-6B의 정적 Spot/S-DoT CSV 검사는 승인된 Area 패널 연결 무결성 확인이며 추천 생성이 아니다.

## 9. 비기능 요구사항

| **ID** | **속성** | **요구** |
| --- | --- | --- |
| NFR-01 | 보안 | API Key는 명시한 .env에서만 읽고 코드·문서·로그·완성 URL에 노출하지 않는다. |
| NFR-02 | 신뢰성 | 원본·메타데이터·회차 증거는 비덮어쓰기 저장하며 부분 파일을 정상 파일로 남기지 않는다. |
| NFR-03 | 감사 가능성 | 요청·Area·회차·버전·경로·크기·SHA-256으로 결과를 재현한다. |
| NFR-04 | 성능·최신성 | 실측 지연 분포와 회차 소요시간을 기록하고 고정 임계치는 반복 관측 후 승인한다. |
| NFR-05 | 가용성 | 무료 공공 API의 SLA 부재와 결측을 정상 운영 위험으로 처리한다. |
| NFR-06 | 유지보수성 | Python 3.12 호환 표준 라이브러리를 우선하고 불필요한 패키지를 추가하지 않는다. |
| NFR-07 | 운영성 | 비개발자 PM이 명령·정상 신호·중단 기준을 복사해 사용할 수 있어야 한다. |
| NFR-08 | 개인정보 | 현재 집계 공개데이터만 사용하고 개인 위치·고객정보를 수집하지 않는다. |
| NFR-09 | 법적 준수 | 공공누리 제1유형의 출처표시와 재배포 범위를 결과 공개 전에 확인한다. |
| NFR-10 | 확장성 | 13개 반복 결과가 정당화할 때만 121개로 확대하며 구조는 Area 목록 주입으로 확장 가능해야 한다. |
| NFR-11 | 복구성 | 완료 Batch를 Google Drive 복사본에서 새 로컬 경로로 복원하고 Manifest로 검증할 수 있어야 한다. |

## 10. 성공 지표와 판정 게이트

### 10.1 Engineering Gate 정의

이 절은 제품 판정 단계를 정의하며 현재 통과·대기 상태를 중복 관리하지 않는다.
현재 Gate와 실행 상태는 `PROJECT_STATUS.md`를 단일 기준으로 확인한다.

| **단계** | **제품 판정 의미** |
| --- | --- |
| EG-0~3 | 문서·기준데이터·샘플·Project Guard 기준 수립 |
| EG-4 | POI072 단일 실제 수집 검증 |
| EG-5 | 대표 3개 Area 실제 수집과 구조 검증 |
| EG-6A | 13개 Area·Spot·S-DoT 참조 패널 확정 |
| EG-6B | 13개 Area 단일 회차 구현·실행·품질 판정 |
| Backup Readiness | EG-6B Live 전 Desktop Sync·Worker·복구 검증 묶음; 새 EG 번호가 아님 |
| EG-7 | 승인된 주기의 동일 13개 Area 반복수집 파일럿 |
| EG-8(상위) | 데이터 분석·예측·추천 준비 상위 Gate |
| EG-8A | Python Loader·정규화·데이터 품질 |
| EG-8B | EDA·서울시 Forecast 평가·Baseline·Feature Dataset |
| EG-8C | 미래 Area 인구·피크 예측 모델 |
| EG-8D | Area Ranking·선택적 S-DoT·Spot Candidate Evaluation(기존 EG-8 정의 계승) |
| EG-8E | Recommendation Output Contract·UI/UX Readiness(Recommendation MVP 구현 Gate 아님) |
| Recommendation MVP Workstream | Gate number `NOT_ASSIGNED`; 검증 Feature와 별도 PM 승인 필요 |

> **상태 해석**  코드 병합과 Gate 통과는 별개다. 현재 구현·실행 증거와 PM 판정은
> `PROJECT_STATUS.md`에서 확인한다.

### 10.2 Gate A·B·C·D

| **게이트** | **판정 대상** | **핵심 기준** | **시점** |
| --- | --- | --- | --- |
| Gate A | 기술적 데이터 타당성 | 안정 수집, 예측 필드, 기준선 대비 유용성, POI 범위 명확성 | 현 PoC |
| Gate B | 인구·소비 시간패턴 | 비관행 피크, 인구·소비 동행, 이동 리드타임, 반복성 | 현 PoC |
| Gate C | 사용자 문제 타당성 | 실제 어려움, 경험 대비 가치, 담당구역·재고·시간 제약 | 후속 인터뷰 |
| Gate D | 현장 성과 타당성 | 추천 이동·고객 접촉·판매 증가 | 후속 실증 |

### 10.3 운영·분석 핵심 지표

- 수집 완전성: expected_area_count, attempted_count, success_count, failure_count, failed_area_codes
- 신뢰성: Area별 실패율, 연속 실패, 스키마 오류, 저장 오류, 파일 무결성 실패
- 최신성: requested_at - population_reference_time 지연 분포와 반복 응답 비율
- 예측: 리드타임별 MAE·RMSE·상대오차·예측범위 포함률·혼잡 등급 일치율
- 패턴: 요일·시간 기준선, 변동성, 피크 지속시간, 비관행 피크 반복 횟수
- 운영성: 한 회차 소요시간, 호출량, 저장공간 증가량, 백업 성공·복구 검증
- 서비스 연결성: 이동 가능한 리드타임, Candidate Evidence Assessment, Area–Spot 해석 적합성, 원격 근거 충족률

## 11. 실험 설계와 데이터 기간

| **단계** | **시점** | **허용 분석** |
| --- | --- | --- |
| 첫 Batch 품질 감사 | 최초 실제 13개 Area 수집 직후 | 저장·Manifest·필드·결측·지연·오류와 EG-6B PASS/보완 |
| 단일 Snapshot 비교 | 품질 감사 통과 직후 | Area별 규모·혼잡·구성·Forecast 방향·상대순위 |
| 초기 EDA | EG-7에서 평일 5영업일 확보 후 | 시간대 평균·중앙값·증감·피크 후보·결측·초기 Forecast 오차 |
| 공식 EG-8 분석(EG-8B/EG-8D) | 4주 기준선 후 5주차 | Area Feature·선택적 S-DoT Feature·Spot Candidate Evaluation(EG-8D)과 Feature 유효성(EG-8B) |

첫 Batch 또는 5영업일 데이터로 반복패턴·판매성과·SPOT 직접 유동인구를 확정하지 않는다.

| **시점** | **판정 목적** | **허용 결론** |
| --- | --- | --- |
| 1주 | API·스키마·수집기 안정화 | 운영 결함과 즉시 수정 필요사항 |
| 2주 | 결측·지연 기준선 | 잠정 품질·패턴 |
| 3~4주 | 동일 요일·시간 반복 | B1 잠정 반복성 |
| 4주 종료 | 최근 4주 기준선 완성 | B2 기준선 |
| 5주 | 전향 평가와 최종 분석 | Gate A/B 판정 자료 |
| 5주 종료 | 표본 부족 여부 확인 | 필요할 때만 1주 연장 |

반복수집 주기는 `Asia/Seoul` 벽시계 기준 5분으로 고정한다. 이는
`PM_APPROVED_FIXED`·`LONG_TERM_OPERATING_BASELINE`이며 10분·15분 대안 비교나
중복률 기반 자동 변경을 하지 않는다. API 호출한도, 한 회차 소요시간, 성공률,
운영 컴퓨터 안정성, 저장 증가와 백업 준비는 5분 주기 채택 여부가 아니라 일일
운영시간대, 24시간 또는 선택 시간 운영, Live 확대 시점을 결정하는 Gate로 사용한다.

## 12. 로드맵과 승인 지점

1. R0 — EG-0~EG-5: 기준선, 오프라인 검증, 여의도와 대표 3개 실제 수집
2. R1 — EG-6A: 13개 Area·Spot·S-DoT 참조 패널 확정
3. R2 — EG-6B 구현: 단일 순차수집, 회차 로그, Manifest, SHA-256, H-706
4. R3 — Google Drive for Desktop Sync 계획, 논리 루트 확인, 즉시 Backup Worker·Fake Batch 검증
5. R4 — EG-6B Live Preflight 재통과, 최대 13회 승인, 첫 Batch·자동 백업·품질 감사
6. R5 — 첫 Batch 구조를 기준으로 CSV 계약·Exporter를 별도 구현하고 누적·재생성을 검증
7. R6 EG-7 — 동일 13개 Area 반복수집 파일럿과 독립 S-DoT 관측 수집 가능성 검토
8. R7 EG-8(상위) — 데이터 분석·예측·추천 준비, 4주 기준선·5주차 Gate A/B 판정을 포함
   - R7A EG-8A: Python Loader·정규화·데이터 품질
   - R7B EG-8B: EDA·서울시 Forecast 평가·Baseline·Feature Dataset
   - R7C EG-8C: 미래 Area 인구·피크 예측 모델
   - R7D EG-8D: Area Ranking·선택적 S-DoT Feature·Spot Candidate Evaluation(기존
     R7 EG-8 정의 계승)
   - R7E EG-8E: Recommendation Output Contract·UI/UX Readiness(Recommendation MVP
     구현이 아님)
9. R8 후속 — Recommendation MVP Workstream(`PLANNED`, Gate number `NOT_ASSIGNED`, 별도 PM 승인)
10. R9 후속 — 화면 기반 사용성 검토, 원격 Spot 근거 검증, 필요 시 121개 확대·Gate D 설계

## 13. 의존성

| **구분** | **의존성** | **해결 시점** |
| --- | --- | --- |
| 외부 데이터 | 서울 실시간 도시데이터 일반 인증키와 API 가용성 | PM 승인 실제 실행 |
| 공식 기준 | 121개 장소 CSV와 13개 참조 패널의 불변성 | 변경 시 별도 Issue |
| 운영 환경 | Python 3.12 호환 로컬 실행·안전한 외부 output-root | 실행 전 확인 |
| 백업 | Google Drive for Desktop Sync 논리 루트와 별도 즉시 Backup Worker | EG-6B Live 선행 준비 |
| CSV | 첫 실제 Batch의 필드·결측·Forecast 구조 | 품질 감사 후 별도 Issue |
| 분석 데이터 | 예측 스냅샷·후속 관측 영속화와 시간 정렬 | EG-7/8 구현 |
| 운영 연결 | 담당구역·이동시간·재고·판매 가능 공간 | 별도 운영기관 확인·Gate C/D |
| 법적 | 공공누리 출처표시·재배포 범위 | 대외 공개 전 확인 |

## 14. 리스크와 대응

| **ID** | **리스크** | **영향** | **대응** |
| --- | --- | --- | --- |
| R-01 | 유동인구를 매출로 오해 | 높음 | 표현 통제·판매 데이터 없이 성과 주장 금지 |
| R-02 | Area가 실제 Spot보다 넓음 | 높음 | Area–Spot 분리·원격 다중근거·선택적 S-DoT 보조·운영 적합성 미확인 표시 |
| R-03 | 예측 발행시각 부재 | 중간 | requested_at을 스냅샷으로 보존하되 명칭 과대해석 금지 |
| R-04 | API 지연·결측·스키마 변경 | 높음 | 품질 지표·원본 보존·명시적 실패 상태 |
| R-05 | 반복수집 중 저장 손실 | 높음 | 불변 저장·Manifest·백업 Gate·복구 시험 |
| R-06 | 중복 실행·호출량 초과 | 높음 | EG-7 잠금·고정 5분 계획·호출예산·Live 할당량 Gate |
| R-07 | 날씨 미래정보 누수 | 높음 | 예보·관측 분리와 point-in-time join |
| R-08 | 문서 상태가 코드보다 뒤처짐 | 중간 | 현재 Branch·PR·Issue·실행 상태를 PROJECT_STATUS 한 곳에서 갱신 |
| R-09 | 5분 자동수집 `ACTIVE`와 24시간 이상 장기 지속성 검증 완료를 혼동 | 중간 | PM이 Apps Script 5분 Trigger의 반복 실행과 데이터 누적을 직접 확인해 5분 자동수집은 `ACTIVE`로 기록하되, 24시간 이상 무중단 지속성은 별도로 `NOT_COMPLETED`로 구분한다. 로컬 EG-7은 상시 Scheduler가 아닌 기술검증·Pilot Runner로 유지 |
| R-10 | 1인 운영 과부하 | 중간 | 최소 필드·표준 라이브러리·승인 단계별 확장 |

## 15. PM 결정 필요사항

- D-01 Google Drive for Desktop Sync 설치·로그인과 `FreshManager-Data/` 논리 루트 접근 가능 여부 확인
- D-02 PROJECT_STATUS에 기록된 선행 Preflight를 확인한 뒤 env-file·output-root·
  실행시각·최대 13회 호출 승인과 결과의 EG-6B PASS·보완 판정
- D-03 `CLOSED · PM_APPROVED`: 5분 벽시계 주기, 대안 제외, 중복 기반 변경 금지,
  장기 기준 5분
- D-03A `OPEN`: 일일 운영시간대, 24시간 또는 선택 시간 운영, 호출예산·용량 Gate,
  첫 1시간 이후 확대 시점
- D-04 Batch 완료 직후 Worker 호출, 원격 확인·보존·복원시험의 세부 운영 승인
- D-05 반복수집 전 동시 실행 잠금과 중단·재개 정책 승인
- D-06 예측·관측 정규화 저장구조와 schema/data version 정책 승인
- D-07 날씨·상권현황을 EG-7에 포함할지, 인구 반복수집 안정화 후 추가할지 결정
- D-08 과거 실행 가이드의 폐기·보관 표시와 PROJECT_STATUS·QUALITY_GATES 상태 정렬 Issue 승인

## 16. 수용 기준과 추적성

### 16.1 문서 기준 수용

- 제품 비전과 현 PoC 범위가 분리돼 있다.
- 121개 장기 후보군과 13개 현재 패널이 혼동되지 않는다.
- EG-6B 구현 완료와 실제 수집·Gate 통과 대기가 구분돼 있다.
- 유동인구·카드소비·S-DoT를 실제 판매효과로 표현하지 않는다.
- 날씨 예보·관측, 예측 스냅샷·대상·후속 관측 시각이 분리돼 있다.
- 현재 구현, 부분 구현, 계획 상태가 요구사항별로 표시돼 있다.
- PM 승인사항과 남은 리스크가 숨겨지지 않는다.

### 16.2 PRD–TRD 추적성

| **PRD 범위** | **TRD 연결** | **설명** |
| --- | --- | --- |
| FR-01~04, 11~12 | TRD 4~12장 | 현행 EG-6B 코드 계약 |
| FR-05~06 | TRD 13~18장 | EG-7 정규화·품질 목표 구조 |
| FR-07~08 | TRD 15~18장 | 날씨·상권 Adapter와 시간 정렬 |
| FR-09~10 | TRD 19~22장 | 분석 파이프라인·관측성·Rollout |
| FR-13 | TRD 16·20~24장과 Cloud Backup Plan | 백업 Worker·상태·복구·운영 목표 |
| FR-14 | TRD 14·19장과 EG6 Area Spot Panel | 추천 문맥과 target level 선택 |
| NFR-01~10 | TRD 10~24장 | 보안·저장·검증·운영·복구 |

## 근거 자료

문서의 사실·상태·계약은 아래 로컬 저장소 자료와 완료 기록을 대조해 작성했다. 경로는 FreshManager 저장소 루트 기준이다.

| **자료** | **사용 목적** |
| --- | --- |
| AGENTS.md | 프로젝트 정의, 범위, 승인, 보안, 데이터 보존의 상위 기준 |
| requirements-definition-freshmanager-poc-v0.4.md | 기존 제품 요구, Gate A~D, 5주 평가 설계 |
| PROJECT_STATUS.md + main Git 상태 | 완료 이력과 현재 구현 기준의 차이 확인 |
| docs/analysis/EG5_DATA_ANALYSIS_REPORT.md | 대표 3개 실제 수집의 확인된 사실과 Feature 후보 |
| docs/product/EG6_AREA_SPOT_PANEL.md | 13개 Area·Spot·S-DoT 연결과 해석 한계 |
| docs/testing/QUALITY_GATES.md | EG-0~EG-8 순서와 통과조건 |
| docs/testing/PROJECT_GUARD_SPEC.md | 검사 ID·상태·종료코드의 유일한 기준 |
| PR #54 / commit 6253cc5 완료 기록 | EG-6B 병합, 19/19 Target, 243/243 Full, Guard 41/46 PASS |

## 부록 A. 용어

| **용어** | **정의** |
| --- | --- |
| Area | 서울시 실시간 도시데이터가 제공하는 공식 공간 단위 |
| Spot Candidate | Area·선택적 S-DoT 또는 대체 동적 근거·공식 공간 Context로 구성하는 판매 후보 위치 |
| 데이터 기반 우선 후보 | 복수 후보의 원격 근거·반복성·최신성·불확실성 조건을 충족한 비교우위 후보; 공식 추천이나 판매 적합성 보장 아님 |
| Candidate Anchor Point | 후보 생성의 출발점; 현재 Spot Master의 역 중심 대리좌표이며 판매 Spot 확정값이 아님 |
| S-DoT | Area 내부 활성 위치 판단을 보조하는 독립 센서 계층; Area 대체값이나 판매량이 아님 |
| 예측 스냅샷 | 한 수집시점에 확보한 미래 예측 묶음 |
| 후속 관측값 | 예측 대상시각이 지난 뒤 API로 다시 받은 서울시 추정 인구 |
| Engineering Gate | 구현 준비도·품질 단계 EG-0~EG-8; EG-8은 EG-8A~EG-8E 하위 Gate로 세분화된 상위 Gate |
| Model Output | EG-8C 예측 모델의 원시 산출값; UI가 직접 참조하지 않음 |
| Recommendation Output | EG-8E Recommendation Output Contract가 정의하는 추천 결과 스키마; Model Output과 UI Presentation 사이의 계층 |
| Recommendation MVP Workstream | `PLANNED`, Gate number `NOT_ASSIGNED`; 별도 PM 승인 전 공식 Gate가 아닌 후속 작업축(EG-8E는 이 Workstream의 구현 Gate가 아니라 계약·설계 준비 Gate) |
| Gate A~D | 데이터·사용자·현장 타당성의 제품 판정 게이트 |
| Project Guard | 문서·데이터·보안·수집 계약의 오프라인 자동검사 |

## 변경 이력

| 버전 | 날짜 | 변경내용 | 승인상태 |
|---|---|---|---|
| v1.2 | 2026-07-29 | 현장검증 불가 전제의 원격 근거 기반 Spot 후보 정책을 반영. 현재 PoC 최대 결과를 데이터 기반 우선 후보로 제한하고 운영 적합성 미검증을 명시 | PM 결정 D-019 |
| v1.1 | 2026-07-24 | EG-8을 상위 Gate로 유지하고 EG-8A~EG-8E로 세분화. PoC 범위에 미래 Area 인구·피크 예측, Area/Spot Ranking, Recommendation Output Contract, UI/UX 설계·와이어프레임·프로토타입을 포함. 판매량·매출 예측, 상용 앱·웹 출시, 실시간 서빙·MLOps는 계속 비목표. §5.2~5.4, §10.1, §12, 부록A 갱신 | PM 결정 |
| v1.0 | 2026-07-22 | 최초 공식 제품 기준 확정 | PM 승인 |
