# Analysis Plan

- 문서 상태: Draft
- 버전: v0.1.11
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-31
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/product/FreshManager_PRD_v1.0.md`
  - `docs/engineering/FreshManager_TRD_v1.0.md`
  - `docs/history/requirements/requirements-definition-freshmanager-poc-v0.4.md` (역사 문서)
  - `docs/rules/DATA_COLLECTION_RULES.md`
  - `docs/data/FIELD_DICTIONARY.md`
  - `docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`
  - `docs/testing/QUALITY_GATES.md`
  - `docs/data/ML_READY_DATASET_SPEC.md`(EG-8A/EG-8B ML-ready 데이터셋 정본)
  - `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`(EG-8E 추천 출력 정본)
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 서울시 공개데이터를 활용해 Freshmanager 유동판매 추천 서비스의 데이터 타당성을 검증하기 위한 분석 질문, 가설, 대상기간, 평가방법 및 Gate 판정기준을 정의한다.

이 문서는 실제 분석을 시작하기 전 다음을 고정한다.

1. 무엇을 분석하는가
2. 무엇을 분석하지 않는가
3. 어떤 데이터를 사용하는가
4. 어떤 시간 단위로 비교하는가
5. 어떤 기준선과 비교하는가
6. 결측과 이상값을 어떻게 처리하는가
7. 어떤 결과를 Gate A·B 판정에 사용하는가
8. 현재 PoC로 증명할 수 없는 것은 무엇인가

---

## 2. PoC 분석 목적

현재 PoC의 목적은 다음을 확인하는 것이다.

1. 서울시 주요 장소 데이터를 안정적으로 수집할 수 있는가
2. 장소별·요일별·시간대별 반복 패턴이 존재하는가
3. 현재 인구와 미래 인구예측을 시간적으로 연결할 수 있는가
4. 서울시 공식 예측이 단순 기준선보다 유용한가
5. 출퇴근·점심 외 추가 피크가 존재하는가
6. 인구 변화와 카드소비 기반 소비활동 변화가 함께 나타나는가
7. 날씨 조건에 따라 인구·소비 패턴이 달라지는가
8. 향후 프레시매니저 서비스 가설 검증에 활용 가능한 데이터 기반이 만들어지는가

---

## 3. 현재 PoC에서 판단하지 않는 내용

다음 항목은 현재 공개데이터 PoC만으로 판단하지 않는다.

- 프레시매니저 실제 매출 증가
- 추천 서비스의 구매전환율
- 추천 위치의 현장 실행 가능성
- 판매원의 이동 의사
- 고객의 실제 구매행동
- 개별 출구·건물 앞 최적 위치
- 프레시매니저 담당구역별 성과
- hy 내부 판매실적
- 추천 알림의 최적 발송시각
- 추천 서비스의 최종 제품성공

이 항목은 향후 현장 인터뷰, 제휴, 실증 또는 내부데이터 연동이 필요하다.

---

## 4. 분석 질문

### 데이터 수집

```text
AQ-1. 현재 승인된 13개 Area 패널을 계획된 범위와 주기로 안정적으로 수집할 수 있으며,
필요성이 확인될 때 121개 Area로 확대할 근거가 있는가?
```

### 시간패턴

```text
AQ-2. 동일 장소에서 요일·시간대별 인구 변화가 반복되는가?
```

### 공식 예측

```text
AQ-3. 서울시 미래 인구예측은 단순 기준선보다 후속 관측값을 더 잘 설명하는가?
```

### 피크

```text
AQ-4. 출퇴근과 점심시간 외에도 반복적으로 나타나는 인구 피크가 존재하는가?
```

### 소비활동

```text
AQ-5. 인구 증가와 카드소비 기반 소비활동 증가가 같은 시간대 또는 일정 시차를 두고 함께 나타나는가?
```

### 날씨

```text
AQ-6. 날씨 조건에 따라 인구·소비 시간패턴이 달라지는가?
```

### 장소 유형

```text
AQ-7. 공원·발달상권·인구밀집지역 등 장소 유형별로 시간패턴이 다른가?
```

### 서비스 활용 가능성

```text
AQ-8. 데이터가 프레시매니저가 행동할 수 있는 시간간격으로 제공되는가?
```

AQ-8은 실제 이동 가능성을 확정하는 질문이 아니라 데이터상 활용 가능한 리드타임을 확인하는 질문이다.

---

## 5. 분석 가설

### H1. 시간패턴 반복성

동일 장소의 같은 요일·시간대 인구에는 반복 가능한 패턴이 존재한다.

### H2. 공식 예측 유용성

서울시 공식 미래 인구예측은 최근값 유지 기준선보다 예측오차가 작다.

### H3. 장소 유형 차이

장소 유형에 따라 피크 발생시각, 지속시간, 변동폭이 다르다.

### H4. 비관행 피크

일부 장소에서는 출퇴근·점심 외에도 반복적인 추가 피크가 존재한다.

### H5. 인구·소비 동행

일부 장소와 시간대에서 인구 증가와 카드소비 기반 소비활동 증가가 함께 나타난다.

### H6. 날씨 영향

비·고온·저온 등 날씨 조건에 따라 인구와 소비활동 패턴이 달라진다.

가설은 분석을 위한 검토대상이며 사실로 미리 확정하지 않는다.

---

## 6. 분석 범위

### 6.1 현재 수집·분석 범위

```text
EG-6A에서 확정한 13개 Area 패널
```

서울시 주요 121장소는 장기 공식 후보군이며 현재 분석 입력으로 가정하지 않는다.

### 6.2 초기 분석 범위

- 여의도와 EG-5 대표 3개 Area
- EG-6A에서 확정한 13개 Area·Spot·S-DoT 패널
- 데이터 품질 기준을 통과한 Area
- 상권현황이 지원되는 Area

### 6.3 후속 분석 범위

13개 Area 단일·반복 수집, EG-8 Feature 분석과 별도 승인된 Recommendation MVP Workstream의 데이터
필요성이 확인되고 PM이 승인한 경우 121개 Area의 장소 유형별·시간대별 비교로 확대한다.

### 6.4 공식 Feature 구조

```text
필수: Area Observation → Area Feature
선택: S-DoT Observation → 지원·접근·수집·품질조건을 통과한 S-DoT Feature
추가: 공간 Context + 원격 Spot 근거
별도 상태: 현장검증 + 운영 제약
결합: Spot Candidate Evaluation
결과: SPOT / AREA + fallback_reason / 추천 없음
```

S-DoT는 Area 내부 활성 위치 판단을 보조하는 독립·선택적 데이터 계층이며 Area 값을
대체하지 않는다. S-DoT 미지원 6개 Area도 Area 분석과 추천 후보에서 제외하지 않는다.
Spot Candidate Evaluation은 고정 판매 위치나 판매효과가 아니라 후속 추천 입력
근거다. Score·가중치·임계값은 `PLANNED` 또는 `OPEN_DECISION`이다.

### 6.5 EG-8B·EG-8C Gate 연결

이 문서의 기존 EDA(§9.3)·Forecast 평가(§18~20)·Baseline(§18) 방법론은
EG-8B(EDA·서울시 Forecast 평가·Baseline·Feature Dataset)에 대응한다. §6.4의
Spot Candidate Evaluation은 EG-8D가 계승한 기존 EG-8 정의와 동일하다.

미래 Area 인구 예측과 피크 발생 여부·예상 피크시각을 다루는 모델링은
EG-8C(미래 Area 인구·피크 예측 모델)에 대응한다. EG-8C는 EG-8B가 만든 Baseline
(B0/B1/B2/서울시 공식 예측) 대비 성능이 확인된 뒤에만 채택한다. 승인된
Linear·Ridge 비교와 신규 공식 Dataset 재평가는 완료됐고 서울시 Forecast
Baseline을 유지했으며 자체 ML은 채택하지 않았다. 새 모델 후보는 별도 Test
구간·추가 데이터와 PM 승인 뒤에만 다시 검토한다.

ML-ready 데이터셋의 상세 스키마·버전 계약은 `docs/data/ML_READY_DATASET_SPEC.md`
가, Recommendation 결과 출력 계약은 `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`가
소유한다. 이 문서는 그 두 문서와 분석 방법론을 중복 정의하지 않는다.

### 6.6 Spot Forecast 분석 가능성 조건

이 문서의 예측 평가(§18~21)는 지금까지 Area 단위를 전제로 한다. Area
Forecast와 Spot Forecast는 별도 분석 단위로 구분하며, 다음 조건을 만족하는
경우에만 Spot Forecast 분석을 검토한다.

- **검증조건**: `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` §5의
  `spatial_support_type`이 `DIRECT_SENSOR` 또는 `NEARBY_SENSOR`인 Spot만
  Spot Forecast 분석 후보로 검토한다. `AREA_INFERENCE`·`UNSUPPORTED` Spot은
  Area Forecast만 사용한다(§3 Prediction Scope와 동일한 경계).
- **DIRECT_SENSOR 평가**: 센서가 Spot을 직접 대표한다고 판단한 근거(설치
  위치·거리·데이터 최신성)를 함께 기록하고, 센서 자체의 결측·오류율도 Area
  데이터와 동일한 품질 기준(§28)으로 관리한다.
- **NEARBY_SENSOR 평가**: 거리가 있는 근사 근거이므로 DIRECT_SENSOR보다 낮은
  신뢰도로 다루며, 예측 표현도 §6.6이 아니라
  `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` §8의 "가능성이 있습니다"
  수준 표현으로 제한한다.
- **AREA_INFERENCE 사용 한계**: Spot 직접 근거 없이 Area 예측만으로 Spot 상태를
  추정하는 경우, 그 추정을 Spot의 직접 관측값처럼 표현하지 않는다(PRD §4
  "Area ≠ Spot" 원칙, 이 문서 §7의 "POI 단위 값은 특정 지하철 출구, 건물 앞,
  흡연부스 앞의 값으로 해석하지 않는다" 원칙과 동일).
- **UNSUPPORTED 처리**: 공간 근거가 전혀 없는 Spot은 Spot Forecast 분석
  대상에서 제외하고, 필요하면 AREA fallback으로만 다룬다.
- **관측 이력 부족 시 AREA fallback**: Spot 단위 관측 이력이 기준 기간(§9~10)
  만큼 축적되지 않은 경우, Spot Forecast를 분석하지 않고 Area Forecast로만
  fallback한다.
- **센서-Spot 거리·대표성 검증**: `support_distance_m`이 클수록 대표성이
  낮아진다고 가정하되, 구체적인 거리 임계값은 아직 확정하지 않는다.
- **동일 Area 내 Spot별 차이 검증**: 같은 Area에 여러 Spot이 연결된 경우, Area
  평균값 하나로 모든 Spot을 같다고 취급하지 않는다. Spot별 차이를 검증하는
  구체 방법은 실제 S-DoT 동적 수집이 구현된 뒤 별도 검토한다.
- **Area 예측값을 Spot Ground Truth로 사용 금지**: Area 예측·관측값은 Spot의
  실제 상태를 검증하는 정답(ground truth)으로 사용하지 않는다. Area 값은
  Spot 상태의 보조 추정치일 뿐이다(D-003 Area First 원칙과 동일 경계).

Spot Forecast의 모델·성능기준·최소 데이터 기간은 임의로 확정하지 않는다.

**상태: `OPEN_DECISION`**

S-DoT 동적 수집 자체가 `NOT_IMPLEMENTED`이므로(D-005), 이 절의 조건은 목표
분석 계획이며 현재 시점에 즉시 적용 가능한 실행 계획이 아니다.

#### 6.6.1 착수 전 사전조건 체크리스트

Spot Forecast 분석에 착수하려면 다음을 **모두** 확인한다. 하나라도
미충족이면 착수하지 않고 Area Forecast만 사용한다.

- [ ] Spot 좌표와 명칭이 검증됨(`docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`
  §9.1 Spot Recommendation Eligibility 통과)
- [ ] 센서 좌표가 확인됨
- [ ] Spot–Sensor 거리가 확인됨(`support_distance_m`)
- [ ] 센서의 Spot 대표성이 검증됨(`spatial_support_type`이 `DIRECT_SENSOR` 또는
  `NEARBY_SENSOR`)
- [ ] 해당 Spot의 과거 관측 시계열이 최소 기간만큼 확보됨(구체 기간은 미확정)
- [ ] Area 값과 독립된 Spot 자체 관측값(Spot Ground Truth)이 확보됨 — Area
  예측값 자체를 Spot Ground Truth로 대체하지 않음
- [ ] 최소 데이터 기간이 PM 승인으로 결정됨
- [ ] `DIRECT_SENSOR`와 `NEARBY_SENSOR` 근거의 예측 성능을 하나로 합치지 않고
  분리 평가할 계획이 있음

이 체크리스트는 §6.6의 원칙(검증조건·DIRECT/NEARBY/AREA_INFERENCE/UNSUPPORTED
평가·AREA fallback·Ground Truth 금지)을 실행 전 확인 항목으로 정리한 것이며
새로운 원칙을 추가하지 않는다.

---

## 7. 장소 분석 단위

기본 장소키:

```text
AREA_CD
```

장소명만으로 데이터를 연결하지 않는다.

POI 단위 값은 특정 지하철 출구, 건물 앞, 흡연부스 앞의 값으로 해석하지 않는다.

Area 관측값, S-DoT 관측값과 Spot Candidate Context는 분리한다. 현재 Spot Master의
`STATION_CENTER_PROXY`는 Candidate Anchor Point이며 현장 검증이 끝난 판매 Spot이
아니다. Area 값을 해당 좌표의 직접 유동인구로 해석하지 않는다. 후속 추천에서
Area 기회와 D-020의 원격 근거 Eligibility가 충분한 Spot Candidate가 확인되면
`target_level=SPOT`을 사용한다. Spot 근거가 부족하고 Area 근거만 충분하면
`target_level=AREA`와 `fallback_reason`을 사용하며, Area 근거도 부족하면
추천하지 않는다. 현장검증·운영 적합성은 별도 상태로 기록한다.

---

## 8. 시간 분석 단위

원본은 PM이 확정한 5분 벽시계 주기로 수집한다. 아래 15분·30분·1시간은 수집주기
대안이 아니라 5분 원본을 분석할 때 사용할 수 있는 집계 구간이다. 10분·15분 수집
주기를 비교하거나 중복률로 5분 주기를 변경하지 않는다.

후보 시간 단위:

- 원본 수집단위
- 15분
- 30분
- 1시간

최종 분석 단위는 다음을 확인한 뒤 PM이 승인한다.

- 실제 데이터 갱신주기
- 13개 Area 1회 수집 소요시간
- 결측률
- 예측 대상시각 간격
- 분석 목적
- 소비활동 데이터 시간해상도

서로 다른 해상도의 데이터를 결합할 때는 더 거친 단위에 맞출 수 있다.

---

## 9. 분석 기간

기본 계획:

```text
1~4주차
→ 데이터 수집
→ 품질검사
→ 패턴 확인
→ 기준선 구축

5주차
→ 아웃오브샘플 평가
→ 최종 비교
→ Gate 판정
```

데이터가 부족할 때만 PM 승인으로 1주 연장한다.

최종 분석과 보고서 작성이 끝날 때까지 데이터를 보관한다.

### 9.1 첫 Batch 데이터 품질 감사

최초 실제 13개 Area Batch 직후에는 다음만 감사한다.

- 성공·실패 Area 수와 실패 목록
- 요청·수신·관측시각과 관측 지연
- 인구 최소·최대, 혼잡도와 필수필드 누락·비정상값
- Forecast 개수·대상시각·파싱 오류
- EXACT·RELATED Area의 해석 차이
- Raw·Metadata·Collection Log·Manifest 파일 수와 SHA-256

결과는 `EG-6B PASS` 또는 `보완 필요` 판정 근거다.

### 9.2 단일 Snapshot 비교

첫 Batch 품질 감사 통과 직후에는 Area별 인구 규모·혼잡도·상주/비상주·연령/성별
구성, Forecast 방향과 동일 시점 상대순위를 비교할 수 있다. 한 회차만으로 시간대
반복패턴, 요일 기준선, Forecast 정확도, 피크 반복성, 판매성과와 Spot 직접 유동인구를
판단하지 않는다.

### 9.3 평일 5영업일 초기 EDA

EG-7에서 평일 5일 데이터가 확보되면 시간대 평균·중앙값, Area별 증감, 피크 후보,
장소 순위 안정성, 결측률, 관측 지연, Forecast 1시간 초기 오차와 S-DoT 지원·미지원
비교 가능성을 탐색한다. S-DoT 동적 관측 수집은 Area 반복수집과 분리해 접근성·
갱신주기·결측·연결 가능성을 먼저 검토한다. 이는 초기 EDA이며 공식 서비스 성능·
판매효과 판정이 아니다.

데이터가 누적되면 다음도 함께 탐색한다(EG-8B 범위).

- 평일·주말 비교(초기 5영업일에는 주말 데이터가 없으므로 후속 주차에서 확인)
- 동일 관측값이 반복되는 비율(중복률)
- Area 간 인구·혼잡 패턴의 상관관계

### 9.4 4주 기준선과 5주차 공식 분석

1~4주 데이터로 요일·시간대 기준선과 Area 변동성·장소 순위 안정성을 만들고,
5주차 데이터로 피크 사전탐지, Forecast 1·3·6시간 오차, S-DoT 보조가치,
Area Feature·선택적 S-DoT Feature·Spot Candidate Evaluation(EG-8D가 계승한 기존
EG-8 정의), SPOT 추천 가능조건과 AREA fallback 적정성을 평가한다. 이 시점을
EG-8(EG-8B/EG-8D) 공식 분석과 PoC 데이터 타당성 판정 시점으로 사용한다.
Recommendation MVP Workstream은 `PLANNED`, Gate number `NOT_ASSIGNED`이며 이
결과와 별도 PM 승인 후 시작한다.

---

## 10. 학습·평가 기간 분리

미래정보 누수를 방지하기 위해 기간을 분리한다.

### 기준선 구축 기간

1~4주 데이터를 이용해 다음을 계산한다.

- 장소별 요일·시간 평균
- 최근 4주 평균
- 변동범위
- 후보 피크
- 기준선

### 평가 기간

5주차 데이터를 기준선 계산에 미리 포함하지 않는다.

5주차는 다음 평가에 사용한다.

- 서울시 공식 예측
- B0
- B1
- B2
- 피크 탐지
- 패턴 재현성

### 10.1 시계열 분할 원칙(EG-8C 모델 검토 전제)

EG-8C에서 자체 예측 모델을 검토할 경우 다음 분할 원칙을 지킨다.

- 무작위(random) 분할을 금지한다.
- Train/Validation/Test는 반드시 시간순으로 분할한다.
- 평가 기간 데이터를 학습 기간에 섞지 않는다(§26 미래정보 누수 금지와 동일 원칙).
- 동일 `forecast_target_time`에 대한 중복 예측은 평가 시 이중 계산하지 않도록
  관리한다(중복 처리 자체는 원본 삭제가 아니라 집계 시 플래그 기반 처리).
- 학습기간과 평가기간을 분리하고, 평가기간 데이터로 만든 통계를 학습 입력에
  역으로 사용하지 않는다.
- Area별 평가와 전체 Area 평가를 분리해서 보고한다. 전체 평균이 양호해도 특정
  Area의 성능 저하를 숨기지 않는다.

이 원칙은 §10의 기존 기준선·평가 기간 분리 원칙을 EG-8C 모델 검토로 확장한
것이며 새로운 상충 규칙을 만들지 않는다.

---

## 11. 사용 데이터셋

| 데이터셋 | 분석 목적 |
|---|---|
| `places` | 장소코드·분류 연결 |
| `population_observations` | 현재 인구 패턴 |
| `population_forecasts` | 공식 예측 평가 |
| `commerce_observations` | 소비활동 대리변수 |
| `weather_observations` | 사후 날씨 조건 분석 |
| `weather_forecasts` | 예측시점 입력조건 |
| `collection_logs` | 수집 품질과 결측 분석 |
| `sdot_observations` | 센서별 시간대 변화와 Area 내부 활성 위치 보조; FUTURE_CONTRACT |
| `spot_candidate_context` | Anchor·공간·현장검증 Context; FUTURE_CONTRACT |
| `spot_candidate_evaluations` | Area·선택적 S-DoT Feature·Context 기반 후보 근거 평가; FUTURE_CONTRACT |

---

## 12. 데이터 포함 조건

다음 조건을 만족하는 데이터를 분석에 포함한다.

- 공식 `AREA_CD`
- 정상 파싱
- 유효한 시간값
- 필수 인구값 존재
- 원본 파일 추적 가능
- `collection_status=success`
- 분석기간 내 데이터
- 스키마 변경 영향이 없음

---

## 13. 데이터 제외 또는 별도 처리 조건

다음 데이터는 제외하거나 별도로 표시한다.

- `api_error`
- `timeout`
- `parse_error`
- `validation_error`
- 잘못된 장소코드
- 필수 시간값 없음
- 기준시각 역전
- 중복 수집
- 스키마 변경 구간
- 장기간 연속 결측
- 상권 미지원 장소
- 사후 수정된 값

제외 건수와 사유를 보고서에 기록한다.

---

## 14. 결측 처리

다음 상태를 구분한다.

```text
missing
not_supported
api_error
parse_error
실제 숫자 0
```

### 원칙

- 결측을 숫자 0으로 바꾸지 않는다.
- `not_supported`를 결측으로 계산하지 않을 수 있으나 별도 집계한다.
- API 오류를 데이터값 결측과 구분한다.
- 보간은 분석 목적별로 별도 승인한다.
- 예측 평가 데이터는 원칙적으로 임의 보간하지 않는다.
- 시각화에서 결측구간을 숨기지 않는다.

---

## 15. 이상값 처리

값이 이상해 보여도 원본에서 삭제하지 않는다.

이상값 후보:

- 이전 시점 대비 급격한 변화
- 최소값이 최대값보다 큼
- 음수 인구
- 기준시각 역전
- 동일 응답 반복
- 장소코드 불일치
- 혼잡도와 인구범위의 극단적 불일치

이상값은 다음으로 구분한다.

- 실제 현상 가능성
- API 오류 가능성
- 파싱 오류
- 중복 수집
- 이벤트 영향
- 스키마 변경

자동 삭제 대신 플래그를 생성한다.

---

## 16. 인구 중심값

현재 인구 중심값:

```text
population_midpoint
= (population_min + population_max) / 2
```

예측 인구 중심값:

```text
forecast_population_midpoint
= (forecast_population_min + forecast_population_max) / 2
```

중심값은 분석용 파생값이며 서울시 원본 필드가 아니다.

---

## 17. 예측 연결 방법

예측값과 후속 관측값을 다음 기준으로 연결한다.

```text
area_code 일치
+
forecast_target_time과 population_reference_time 일치 또는 허용범위 내 근접
```

시간이 정확히 일치하지 않을 경우 허용 오차범위를 별도로 정의한다.

임의로 가장 가까운 값을 연결하기 전에 다음을 확인한다.

- 데이터 수집간격
- 기준시각 지연
- 예측 대상시각 간격
- 허용 가능한 시간차

---

## 18. 예측 기준선

### B0. 최근값 유지

예측시점의 최근 관측값이 미래에도 유지된다고 가정한다.

```text
미래 예측값
= 예측시점의 최근 관측값
```

### B1. 같은 요일·같은 시간

이전 같은 요일·시간의 값을 사용한다.

예:

```text
이번 주 화요일 12시
→ 지난주 화요일 12시
```

### B2. 최근 4주 같은 요일·시간 평균

최근 4주 같은 요일·시간 중심값의 평균을 사용한다.

### 서울시 공식 예측

서울시가 제공한 미래 인구예측을 사용한다.

### 비교 순서

```text
B0
→ B1
→ B2
→ 서울시 공식 예측
```

자체 머신러닝은 위 비교가 끝난 뒤 필요성이 확인된 경우에만 검토한다.

---

## 19. 예측 리드타임

주요 평가 리드타임 후보:

- 1시간
- 3시간
- 6시간

실제 API 예측시각 구조에 따라 평가 가능한 리드타임을 확정한다.

리드타임:

```text
forecast_target_time
-
forecast_snapshot_time
```

---

## 20. 예측 평가 지표

### 20.1 MAE

예측 중심값과 후속 관측 중심값의 절대오차 평균.

사용 목적:

- 평균적인 오차규모 확인
- 기준선 간 비교

### 20.2 RMSE

큰 오차에 더 큰 가중치를 주는 지표.

사용 목적:

- 큰 예측 실패 비교

### 20.3 상대오차

장소별 인구규모 차이를 고려하기 위한 지표.

인구가 매우 적은 구간에서는 값이 불안정할 수 있으므로 주의한다.

### 20.4 예측 구간 포함률

후속 관측 중심값 또는 관측범위가 서울시 예측범위 안에 포함되는 비율.

### 20.5 혼잡도 등급 일치율

공식 예측 혼잡도와 후속 관측 혼잡도가 일치하는 비율.

### 20.6 리드타임별 오차

- 1시간
- 3시간
- 6시간

각 리드타임별 오차를 별도로 보고한다.

성공 임계값은 초기 데이터 분포와 기준선 결과를 확인한 뒤 PM이 승인한다.

---

## 21. 피크 정의

피크는 단순히 가장 높은 값 한 개를 의미하지 않는다.

후보 조건:

1. 동일 장소·요일·시간 기준보다 높음
2. 일정 시간 이상 지속
3. 일회성이 아니라 반복 발생
4. 결측이나 API 오류가 아님
5. 출퇴근·점심 피크와 구분 가능

피크 판단 기준 후보:

- 평균 대비 증가율
- 평균 대비 표준편차
- 상위 백분위
- 연속 지속시간
- 반복 발생 횟수

구체 임계값은 데이터 분포를 확인한 뒤 버전 업데이트로 승인한다.

### 21.1 피크 탐지 성능 지표(EG-8C)

위 피크 정의는 관측된 데이터에서 무엇을 피크로 볼지 정의한다. EG-8C가 미래
피크를 예측하는 모델을 검토할 경우, 그 예측 성능은 다음 별도 지표로 평가한다.

- 피크 발생 탐지: 실제 피크가 발생한 시점을 모델이 피크로 예측했는지 여부
  (탐지율·오탐률)
- 피크 시각 오차: 예측한 피크 시각과 실제 피크 시각의 차이
- 조기 탐지 시간: 실제 피크 발생 전 얼마나 일찍 피크를 예측했는지(리드타임)

이 지표들의 목표 수준(예: 허용 탐지율, 허용 시각 오차)은 아직 확정하지 않는다.

**상태: `OPEN_DECISION`**

---

## 22. 출퇴근·점심 시간 구분

초기 참고구간:

- 출근
- 점심
- 퇴근

정확한 시간대는 장소별 패턴 확인 후 확정한다.

모든 장소에 동일한 피크시간을 강제하지 않는다.

---

## 23. 인구와 소비활동 동행 분석

상권현황은 카드소비 기반 소비활동 대리변수다.

분석 가능한 내용:

- 같은 시간대 증가·감소 방향
- 일정 시차 후 소비활동 변화
- 장소 유형별 차이
- 요일별 차이
- 날씨 조건별 차이

다음 결론을 내리지 않는다.

```text
상관관계
= 인과관계

소비활동 증가
= 야쿠르트 매출 증가
```

---

## 24. 시차 분석

인구 변화와 소비활동 사이에 시차가 있을 수 있다.

후보 시차:

- 같은 시간대
- 15분 후
- 30분 후
- 1시간 후

이 목록은 고정 5분 수집주기를 바꾸는 후보가 아니라 분석 시점 간 관계를 보는
후행 구간이다.

실제 데이터 해상도에 따라 후보를 조정한다.

여러 시차를 무제한 탐색해 우연한 상관관계를 선택하지 않는다.

---

## 25. 날씨 조건 분석

날씨 조건 예:

- 맑음
- 비
- 고온
- 저온
- 강풍
- 높은 습도

분석 내용:

- 날씨별 인구패턴 차이
- 소비활동 차이
- 공식 예측오차 차이
- 피크 지속시간 차이

예측 평가에는 당시 이용 가능했던 날씨 예보만 사용한다.

실제 관측 날씨는 사후 분석에 사용한다.

---

## 26. 미래정보 누수 금지

다음 행위를 금지한다.

- 사후 날씨 관측을 과거 예측 입력에 사용
- 평가기간을 기준선 계산에 미리 포함
- 후속 관측값을 예측값 수정에 사용
- 가장 잘 나온 기간만 선택
- 결과를 본 뒤 가설을 사전가설처럼 표현
- 미래 데이터를 과거 시점 특징으로 사용

---

## 27. 장소 유형별 분석

공식 분류:

- 관광특구
- 고궁·문화유산
- 인구밀집지역
- 발달상권
- 공원

비교 항목:

- 평균 인구범위
- 변동폭
- 피크 발생시각
- 피크 지속시간
- 예측오차
- 결측률
- 상권현황 지원 여부
- 날씨 민감도

---

## 28. 데이터 품질 분석

Gate A에서 다음을 우선 분석한다.

- 예정 수집 대비 실제 수집률
- 장소별 성공률
- 장소별 실패율
- 결측률
- 연속 실패
- 원본 저장 성공률
- 파싱 성공률
- 기준시각 지연
- 예측·관측 연결률
- 상권 지원 장소 수
- 날씨 데이터 연결률

데이터 품질이 기준을 통과하지 않으면 패턴분석 결과를 확정하지 않는다.

---

## 29. Gate A 판정

Gate A는 기술적 데이터 타당성을 평가한다.

### 확인항목

- 승인된 13개 Area 수집 가능성과 후속 121개 확대 근거
- 호출 성공률
- 결측률
- 원본 보존
- 현재값 저장
- 미래예측 저장
- 같은 미래시점 예측 스냅샷 보존
- 예측과 후속 관측 연결 가능성
- 날씨 예보·관측 분리 가능성
- 상권현황 지원 범위
- 반복수집 안정성
- 데이터 지연

### 판정

- PASS
- CONDITIONAL PASS
- FAIL

구체 임계값은 EG-7 및 반복수집 시험 결과를 확인한 뒤 PM이 승인한다.

### 29.1 EG-8C 모델 검토

잠긴 EG-8C Run #2 Dataset과 승인된 Modeling Plan으로 인구 중간값의 잠정 성능
비교를 수행한다. 입력은 승인 Feature 28개, Label은 `label_value`, Split은 잠긴
TRAIN·VALIDATION을 그대로 사용하며 Test Split은 만들지 않는다.

구현 후보는 Linear Regression과 Ridge Regression 두 개다. Area와 혼잡도는
One-hot Encoding, Boolean은 0/1, 나머지 수치는 Scaling하며 전처리 적합과 Ridge
alpha 선택은 TRAIN에만 사용한다. Baseline과 모델은 동일 Validation 행에서
MAE·RMSE·Median Absolute Error를 전체·60분·180분·Area별로 비교한다.

잠정 통과 조건은 가장 강한 Baseline보다 전체 MAE가 낮고 RMSE가 악화되지 않는
것이다. 충족 모델이 없으면 가장 강한 Baseline을 유지한다. 이 비교는 공식 모델
채택이 아니며 추가 장기 데이터와 Test Split을 확보한 뒤 별도 Model Gate에서
판단한다.

2026-07-27 1회 실행 결과, 가장 강한 Baseline은 서울시 Forecast였고 Linear와
Ridge 모두 잠정 통과 조건을 충족하지 못했다. 따라서 서울시 Forecast를 잠정
유지한다. 전체 Validation MAE/RMSE는 현재 인구 유지 6,326.68/12,527.96,
서울시 Forecast 1,917.91/3,749.82, Linear 4,808.54/8,210.75, Ridge
4,694.37/8,666.90이었다. 평가는 계속 `PROVISIONAL`, 공식 Model Gate 판단은
`null`이다. 현재 Label에 없는 피크 예측은 구현하지 않았다.

위 Ridge `alpha` 자동 선택은 2026-07-27 실행의 이력이다. Issue #120·PR #121의
최신 PM 결정에 따라 신규 공식 데이터 Run
`d5e888ef-7514-4f3a-83f5-7820dec58088`의 재평가는 Ridge `alpha=100.0`을 고정하고
자동 탐색 없이 수행했다. 모델 실행 Run은 `eg8c-ml-20260729T075003-kst`, 결과 명세
SHA-256은 `e1447b534091a8dfdb5003a707abfb6f53caf68b549ffa952b760f83ed7f0a0d`다.

2026-07-29 재평가의 평균 절대오차는 다음과 같다.

| 비교 대상 | 전체 | 60분 | 180분 |
|---|---:|---:|---:|
| 현재값 유지 기준 예측 | 6,728.58 | 3,663.88 | 10,085.16 |
| 서울시 미래 예상값 기준 예측 | 1,467.48 | 1,012.37 | 1,965.93 |
| Linear Regression | 4,922.21 | 4,148.25 | 5,769.87 |
| Ridge Regression | 4,875.42 | 3,864.94 | 5,982.12 |

전체 평균 제곱근 오차는 현재값 유지 12,563.84, 서울시 미래 예상값 2,902.07,
Linear Regression 7,939.04, Ridge Regression 8,262.77이었다.

서울시 미래 예상값 기준 예측이 전체·60분·180분과 13개 Area 모두에서 가장
정확했다. 따라서 최종 판단은 `BASELINE_RETAINED`이며 Linear Regression과 Ridge
Regression은 채택하지 않고 현재 PoC의 추가 조정을 종료한다. 별도 최종 시험구간은
만들지 않았고 `evaluation_status=PROVISIONAL`,
`data_sufficiency_status=PROVISIONAL_SPLIT_ONLY`, `test_split_created=false`,
`official_model_gate_judgment=null`을 유지한다. 운영 사용·사용자 게시·공식 추천은
허용하지 않는다.

자체 모델은 여러 주 또는 여러 달의 데이터, 별도 최종 시험구간, 날씨·행사 등 새
입력자료, 실제 방문·판매·매출 자료, 서울시 미래 예상값 오차보정 문제의 별도 정의가
생기고 PM이 새로 승인한 경우에만 다시 검토한다.

**상태: `PROVISIONAL_BASELINE_RETAINED`**

### 29.2 EG-8D Area 예상 유동인구 변화 순서

이 기능은 Issue #109·PR #110으로 `main`에 반영됐다.

EG-8C에서 잠정 유지한 서울시 Forecast와 잠긴 EG-8C Run #2 입력 Snapshot으로
승인된 13개 Area의 60분·180분 후 예상 유동인구 변화 순서를 각각 계산한다. 현재와
미래 인구 대표값은 범위의 중간값을 사용하고, 예상 증가 인구는 미래 중간값에서
현재 중간값을 뺀 값, 예상 증가율은 예상 증가 인구를 현재 중간값으로 나눈 값이다.
현재 중간값이 0이면 증가율을 0으로 대체하지 않고 계산 불가로 기록한다.

서울시 Forecast는 `collection_run_id`·Area 코드·예측 기준시각·예측 대상시각이
모두 같은 행만 정확히 연결한다. 각 시간간격은 양의 증가를 먼저 두고, 예상 증가
인구 내림차순, 미래 중간값 내림차순, Area 코드 오름차순으로 정렬한다. 미래 예상
인구 규모 순위는 별도로 계산하며 두 순위를 가중치로 합치지 않는다.

입력 회차는 호출자가 지정하지 않는다. `LATEST_COMPLETE_LOCKED_SNAPSHOT` 정책이
잠긴 Dataset의 각 `collection_run_id`를 순위 계산 전에 검사하고, 승인된 13개 Area의
유효 Current가 하나씩 있으며 같은 `observed_at`에서 각 Area의 정확한 60분·180분
유효 Forecast가 하나씩 있는 완전 회차만 후보로 삼는다. `observed_at`을 Prediction
Origin과 같은 정본 시각으로 사용해 가장 최신인 회차를 선택하며, 최신 시각이
동률이면 임의 선택하지 않고 실패한다.

#### 29.2.1 Horizon별 데이터 최신성 잠정 Gate

이 Gate는 Issue #111·PR #112로 `main`에 반영됐다.

Area 계산 뒤 실제 표시와 후속 사용 가능 여부는 `evaluation_time`을 기준으로
60분·180분 Horizon별로 따로 판정한다. 모든 시각은 `Asia/Seoul` timezone-aware
값이어야 한다. 공개 Runtime Builder와 CLI는 평가시각·모드·게시 표식을 받지 않는
Runtime 전용 경로만 사용한다. 이 경로가 실행 시작에 서울 시스템 현재시각을 한 번
확보해 `RUNTIME`·`SYSTEM_CLOCK_ASIA_SEOUL`과 운영 게시정책을 고정한다. 공통
실행부는 이렇게 이미 확정된 내부 실행 맥락만 받으며 원시 `evaluation_time`·
`evaluation_mode`·게시 표식을 받지 않는다. 따라서 `None`을 Runtime 시각으로
해석하거나 시스템 현재시각을 읽어 Runtime을 시작할 수 없다. 평가시각을 주입하는 내부
경로는 `HISTORICAL_AUDIT`·`SYNTHETIC_VALIDATION`만 허용한다. 과거 또는 현재와 같은
시각과 일관된 Runtime 표식을 전달해도 주입 경로의 `RUNTIME`은 계약 오류로 차단한다.

세 시간지표는 다음과 같다.

- Snapshot 경과시간: `evaluation_time - selected_complete_observed_at`
- 완전성 지연: `latest_available_current_observed_at - selected_complete_observed_at`
- Horizon 잔여시간: `forecast_target_at - evaluation_time`

| Horizon | `FRESH` | `DEGRADED` | 그 외 |
|---:|---|---|---|
| 60분 | 경과·지연 각각 15분 이하, 잔여 45분 이상 | `FRESH`가 아니고 경과·지연 각각 30분 이하, 잔여 30분 이상 | `STALE_BLOCKED` |
| 180분 | 경과·지연 각각 15분 이하, 잔여 165분 이상 | `FRESH`가 아니고 경과·지연 각각 60분 이하, 잔여 120분 이상 | `STALE_BLOCKED` |

`FRESH`는 Area 표시와 Spot 내부평가가 가능하고, `DEGRADED`는 기준시각·대상시각·
잔여시간·최신 데이터가 아닌 Area 참고정보라는 경고와 함께 Area만 표시할 수 있다.
`STALE_BLOCKED`는 해당 Horizon의 Area 표시와 Spot 후속 사용을 모두 차단한다.
공식 Recommendation은 모든 상태에서 계속 차단한다. 최신성 실패를 이유로 다른
회차를 다시 선택하지 않는다.

완전 Snapshot이 없으면 두 Horizon은 `NO_COMPLETE_SNAPSHOT`이며 Forecast 순위를
생성하지 않는다. Run Builder는 최신 Current 회차의 승인된 13개 Area가 각각
정확히 하나인지와 인구 범위·시각 계약을 검증한다. 공개 `RUNTIME`이고 최신 Current가
15분 이내인 경우에만 현재 인구 범위·중간값·혼잡도·기준시각·경과시간을 담은
Current-only 표시를 허용한다. 결과는 `current_area_state.csv`·JSON·Metadata·전용
Manifest 네 파일 계약이며 Forecast·60분/180분 변화·순위·Spot·공식 추천·판매 기회
표현을 포함하지 않는다. 15분 초과와 `HISTORICAL_AUDIT`는 같은 전용 계약에 표시
불가 사유를 기록하되 모든 사용자 표시·Spot·추천 플래그를 차단한다. Current 누락·
중복, 파싱 실패, timezone-naive 또는 서울 외 시간대, 미래 Current와 시간 역전은
공개 전에 실패한다.

Current-only 행은 `CURRENT_AREA_STATE_ONLY_V1`·`CURRENT_STATE_ROW`로 식별한다.
실제 Runtime 결과는 `operational_observation=true`이고 합성 결과가 아니며, 합성
검증 결과는 `SYNTHETIC_CURRENT_ONLY_VALIDATION`·`synthetic_validation=true`·
`operational_observation=false`로 Metadata와 Manifest 모두에 기록한다. 합성 결과는
정책상 허용 여부를 `simulated_policy_outcome`으로만 보존하며 사용자 표시·운영 게시·
운영 통계 사용은 모두 금지한다.

이 임계값은 PoC 잠정값이며 운영 SLA가 아니다. 과거 1,027회에는
`collection_purpose`, `run_mode`, `environment`, `schema_version`,
`collector_runtime`, `is_test`가 없어 운영 모집단 성공률을 판정하지 않는다.
필드 추가는 별도 수집 계약에서 다루며 이번 변경은 수집 스키마를 바꾸지 않는다.

잠긴 Dataset의 같은 14:00 완전 Snapshot과 14:15 최신 Current를 사용한 역사 검증에서
14:15 평가는 60분·180분 모두 `FRESH`, 14:35 평가는 60분
`STALE_BLOCKED`·180분 `DEGRADED`, 다음 날 07:43 평가는 두 Horizon 모두
`STALE_BLOCKED`였다. 세 결과는 실제 생성시각과 과거 평가시각을 분리한
`HISTORICAL_AUDIT`로 저장소 밖 별도 Result Root에 새 Run으로 보존하며 사용자 표시
적격 결과로 사용하지 않는다.

생산 Builder 통합시험은 공개경로가 서울 시스템 평가시각을 한 번만 사용하고 완전
Snapshot 경로에서 Area 표시·Spot 내부평가 조건을 기록하되 공식 추천은 계속
차단함을 확인했다. 보완 전 합성 사례 D(10분)와 E(16분)는 기존 결과로 보존했으며,
전용 Manifest SHA-256은 각각
`a68edc5771e15126fd4da7bc3bf4591ea31225f7f09a470920735d37cc136ad0`,
`93ed146a0eead42aa5cb958ae1c0938ffea28a60ed00c4d73940f61d9cab2c2d`다.
식별 보완 후 합성 Fixture로 각 1회 생성한 D2
`eg8d-area-priority-20260728T134259-kst`는 `CURRENT_ONLY_ALLOWED`, E2
`eg8d-area-priority-20260728T134301-kst`는 `CURRENT_ONLY_BLOCKED` 정책 결과를
기록했다. 두 결과의 실제 사용자 표시·운영 게시·운영 통계 플래그는 모두 false이며,
전용 Manifest SHA-256은 각각
`f743bc49955e7443e44ad7a331c7dbafae403093216d77d5fb8dc6db3970fa2b`,
`11d1ff201926a2a77a56559cb27ae06c6340144b2640815590b1077b8de946e9`다.
Runtime 전용 경로와 평가시각 주입 경로를 분리한 뒤에도 D2·E2는 허용된
`SYNTHETIC_VALIDATION` 경로의 비운영 결과로 현재 계약을 그대로 충족한다.
공통 실행부 Signature와 직접 호출 회귀시험은 과거시각 또는 `None`과 원시
`RUNTIME` 조합을 전달할 수 없고, 공통 실행부가 시스템 시계를 읽지 않으며 실패 시
결과 디렉터리·Metadata·Manifest를 만들지 않음을 확인한다. 이로써 마지막 내부
Runtime 시작 계약 문제를 해소했다.
실제 Builder 입력에서 고정 `+09:00` offset만 가진 시각을 만드는 경로는 확인되지
않았다. 해당 입력을 향후 허용하려면 Core Gate를 완화하지 않고 입력 경계에서
`ZoneInfo("Asia/Seoul")`로 정규화하는 별도 변경이 필요하다.

2026-07-28 결정적 선택 보완 후 오프라인 결과 Run
`eg8d-area-priority-20260728T074335-kst`는 잠긴 Dataset의 전체 1,027회 중 완전한
86회를 확인하고 기존과 같은 회차 `6ebf1dab-8494-44e0-b598-80248f7f6ff0`을 자동
선택했다. 기존 Run `eg8d-area-priority-20260728T003701-kst`는 변경 없이 보존했다.
새 Run에서 60분·180분 각각 13개 Area가 처리됐고
제외 Area는 없었다. 60분은 양의 증가 1개·중간값 변화 0인 Area 8개·감소 4개이며,
예상 변화 순서 1위는 잠실역(예상 +2,000명), 최하위는 서울역(예상 -2,000명)이었다.
180분은 양의 증가 0개·중간값 변화 0인 Area 3개·감소 10개이므로 양의 증가 후보가
없다. 정렬 규칙상 잠실역(변화 0명)이 1위, 명동 관광특구(예상 -12,000명)가
최하위지만, 이 1위는 전체 표시·우선 검토 순서일 뿐 판매 추천 1위가 아니다.

변화 0은 현재·미래 인구 범위의 중간값 차이가 0이라는 뜻이며 실제 변화가 전혀
없거나 예측범위의 불확실성이 제거됐다는 뜻이 아니다. 이 결과는 한 번의 수집 회차
Snapshot만 사용하므로 장기 반복성과 사용자 가치를 검증하지 않는다.

이 결과는 `PROVISIONAL` Area 분석 산출물이며 공식 Recommendation Output이 아니다.
실제 방문이나 판매 성공을 보장하지 않는다.
Spot·S-DoT·이동시간·담당구역·판매량·매출·구매전환·추천효과는 포함하지 않고,
EG-8D의 Spot Candidate Evaluation과 EG-8E 공식 출력 계약 적용은 별도 PM 승인 후
진행한다.

**상태: `IMPLEMENTATION_AVAILABLE_ON_MAIN` · 결과 `PROVISIONAL` · 공식 Recommendation 아님**

---

## 30. Gate B 판정

Gate B는 인구·소비 시간패턴의 분석 타당성을 평가한다.

### 확인항목

- 요일·시간대 반복 패턴
- 장소 유형별 차이
- B0·B1·B2 대비 공식 예측 유용성
- 1·3·6시간 리드타임별 오차
- 출퇴근·점심 외 피크
- 인구·소비활동 동행
- 날씨 조건별 차이
- 데이터상 활용 가능한 시간간격

Gate B에서 실제 판매량이나 매출효과를 판정하지 않는다.
날씨와의 관계가 발견되지 않았다는 사실만으로 Gate B 전체를 FAIL 처리하지 않고
독립된 분석 결과로 기록한다.

---

## 31. Gate C 판정

Gate C는 사용자 가치와 현장 활용 가능성을 평가한다.

필요한 검증:

- 프레시매니저 실제 인터뷰
- 담당구역 운영방식
- 추천 위치 이동 가능성
- 필요한 리드타임
- 정보 수용성
- 업무 방해 가능성
- 신규·고성과·저성과·이탈 사례 비교

현재 근거상태는 다음과 같다.

| Source Type | 상태와 사용 경계 |
|---|---|
| `PM_CONFIRMATION` | `actual_interview_execution_status=PM_CONFIRMED`; 실제 인터뷰 수행 사실만 확인 |
| `GIT_TRACKED_REPOSITORY_EVIDENCE` | `repository_evidence_status=NOT_TRACKED`; 개인정보 없는 실제 Evidence Summary·외부 참조 없음 |
| `SYNTHETIC_SUPPORTING_MATERIAL` | `synthetic_matrix_status=NOT_ACTUAL_INTERVIEW_EVIDENCE`; `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md`는 공개자료 기반 합성자료이며 실제 인터뷰·직접 인용·Gate C 통과 근거가 아님 |
| `GATE_C_EVALUATION` | `gate_c_status=SEPARATE_EVALUATION_REQUIRED`; 실제 인터뷰 수행 사실만으로 Gate C 통과를 선언하지 않음 |

---

## 32. 분석 산출물

### Gate A

- 데이터 수집 현황표
- 장소별 성공률
- 결측률
- 오류유형
- 지연시간
- 예측·관측 연결률
- 지원범위 표
- Gate A 판정표

### Gate B

- 장소별 시간대 차트
- 요일별 패턴 차트
- 유형별 비교
- 기준선 성능표
- 리드타임별 예측오차
- 피크 후보 목록
- 인구·소비활동 동행표
- 날씨 조건별 결과
- Gate B 판정표

### 최종 보고

- 확인된 사실
- 확인되지 않은 가설
- 데이터 한계
- 서비스 적용 가능성
- 추가 데이터 필요사항
- 현장검증 필요사항
- 다음 단계 권장안

---

## 33. 시각화 원칙

차트는 해석을 명확히 해야 한다.

권장 차트:

- 시간대별 선그래프
- 장소별 막대그래프
- 리드타임별 오차 막대그래프
- 결측률 막대그래프
- 요일·시간 Heatmap
- 예측값과 후속 관측값 비교선

금지 또는 주의:

- 축을 잘라 과장
- 서로 다른 단위를 같은 축에 표시
- 결측구간을 연결선으로 숨김
- 실제 매출처럼 표현
- 예측값과 관측값을 구분하지 않음
- 표본 수를 표시하지 않음

---

## 34. 분석 결과 표현

결과는 다음 세 가지로 구분한다.

### 확인된 사실

데이터와 검증으로 직접 확인된 내용.

### 해석

확인된 결과를 바탕으로 한 분석자의 해석.

### 가설

추가 검증이 필요한 가능성.

세 내용을 같은 수준의 사실로 표현하지 않는다.

---

## 35. 한계

현재 PoC의 한계:

- 서울시 인구는 추정값
- POI와 실제 담당구역이 다를 수 있음
- POI는 특정 출구나 건물 앞 보행량이 아님
- 카드소비는 실제 야쿠르트 매출이 아님
- 비제휴 상태로 실제 판매량 확인 불가
- 사용자 행동과 이동 가능성 확인 불가
- 공개데이터 지원 장소가 다를 수 있음
- 데이터 갱신 지연이 존재할 수 있음
- 짧은 수집기간에는 계절성을 확인하기 어려움
- 이벤트와 일시적 현상을 일반화할 위험이 있음

---

## 36. 분석계획 변경

다음 변경은 PM 승인사항이다.

- 분석 질문 추가·삭제
- 가설 변경
- 분석기간 변경
- 평가기간 변경
- 시간단위 변경
- 기준선 변경
- 평가지표 변경
- 성공 임계값 변경
- 결측 처리 변경
- 피크 정의 변경
- Gate 판정기준 변경

결과를 본 뒤 유리한 방향으로 기준을 변경하지 않는다.

변경이 필요한 경우 변경 전·후 기준과 이유를 기록한다.

---

## 37. 분석 시작 전 체크리스트

- [ ] EG-1 공식 장소 CSV 검증 완료
- [ ] EG-2 샘플 JSON 검증 완료
- [ ] EG-3 Project Guard 구현 완료
- [ ] 공식 필드 정의 완료
- [ ] 시간필드 의미 확인
- [ ] 원본·분석용 데이터 분리
- [ ] 결측 상태 정의
- [ ] 분석기간 확정
- [ ] 기준선 확정
- [ ] 평가기간 분리
- [ ] 미래정보 누수 방지 규칙 확인
- [ ] PM 승인

---

## 38. 완료 정의

ANALYSIS_PLAN은 다음 조건을 만족해야 Approved 상태로 전환할 수 있다.

- 분석 목적 명확
- 분석 제외 범위 명확
- 분석 질문 정의
- 가설 정의
- 대상기간 정의
- 포함·제외 조건 정의
- 결측·이상값 처리 정의
- 기준선 정의
- 평가 지표 정의
- 미래정보 누수 방지
- Gate A·B·C 구분
- 한계 명시
- PM 승인

---

## 39. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.11 | 2026-07-31 | PR #110·#112의 EG-8D 구현상태와 EG-8C 서울시 Forecast Baseline 유지 결론을 반영하고, 실제 인터뷰 PM 확인·Git Evidence 미추적·합성 Matrix 비증거·Gate C 별도 평가 경계를 분리 | 신동현 | PM 변경 승인 |
| v0.1.10 | 2026-07-29 | §29.1에 신규 공식 데이터 재평가를 과거 결과와 구분해 추가; Ridge `alpha=100.0` 고정, 서울시 미래 예상값 기준 예측 유지, 자체 모델 미채택·추가 조정 종료와 재검토 조건 기록 | 신동현 | PM 최종 결정 |
| v0.1.9 | 2026-07-28 | EG-8D 공개 Runtime의 평가시각·모드 주입을 제거하고, Runtime 전용 시스템 시계 경로와 RUNTIME을 금지한 내부 감사·합성 주입경로, Current-only 행 유형과 합성 D2/E2 비운영 식별 계약을 §29.2.1에 반영 | 신동현 | PM 변경내용 검토 전 |
| v0.1.8 | 2026-07-28 | EG-8D 60분·180분 Horizon별 `evaluation_time` 기반 최신성 잠정 Gate와 생산 Builder의 Current-only 전용 계약·Runtime 통합시험·사례 D/E를 §29.2.1에 추가; 공식 Recommendation과 수집 스키마는 변경하지 않음 | 신동현 | PM 변경내용 검토 전 |
| v0.1.7 | 2026-07-28 | EG-8D 서울시 Forecast 기반 60분·180분 Area 예상 유동인구 변화·미래 인구 규모 독립 순위와 Horizon별 변화 요약을 §29.2에 반영; 양의 증가가 없는 180분 결과, 중간값·단일 Snapshot 한계와 공식 Recommendation Output·Spot·판매효과 제외 명시 | 신동현 | PM 변경내용 검토 전 |
| v0.1.6 | 2026-07-27 | EG-8C 잠정 인구 중간값 회귀의 승인 입력·두 Baseline·Linear/Ridge·TRAIN 전용 전처리·Validation 판단과 1회 실행 결과를 §29.1에 반영; 서울시 Forecast 잠정 유지, 공식 Model Gate 미판정, 피크 예측 제외 | 신동현 | PM 변경내용 검토 전 |
| v0.1.5 | 2026-07-24 | Spot Forecast 착수 전 사전조건 체크리스트(§6.6.1) 추가 — Spot 좌표·명칭 검증, 센서 좌표·거리·대표성 확인, Spot별 시계열·Ground Truth 확보, 최소 데이터기간, DIRECT/NEARBY 분리평가를 실행 전 확인 항목으로 정리 | 신동현 | PM 결정 |
| v0.1.4 | 2026-07-24 | Spot Forecast 분석 가능성 조건(§6.6) 추가 — DIRECT_SENSOR/NEARBY_SENSOR/AREA_INFERENCE/UNSUPPORTED 평가 원칙, Area 예측값의 Spot Ground Truth 사용 금지, 모델·성능기준 OPEN_DECISION | 신동현 | PM 결정 |
| v0.1.3 | 2026-07-24 | EG-8B·EG-8C Gate 연결(§6.5), 시계열 분할 원칙(§10.1), 피크 탐지 성능 지표(§21.1), EG-8C 모델 OPEN_DECISION(§29.1) 추가; 기존 EG-8 표현을 EG-8B/EG-8D로 정렬 | 신동현 | PM 결정 |
| v0.1.2 | 2026-07-23 | 15분·30분·1시간 분석 집계·시차를 PM 확정 5분 수집주기 대안과 명확히 분리 | 신동현 | PM 최종 결정 |
| v0.1.1 (Issue #58 보완) | 2026-07-22 | 첫 Batch·5영업일·4주/5주차 분석과 Area·선택적 S-DoT·Spot Candidate Evaluation·후속 Recommendation 경계 정렬 | 신동현 | PM Diff 검토 전 |
| v0.1.0 | 2026-07-17 | 최초 분석계획 초안 작성 | 신동현 | Draft |
