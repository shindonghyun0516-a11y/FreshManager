# FreshManager Project Status

## 1. 문서 역할

이 문서는 현재 Branch·Pull Request·Issue·외부 실행·검증·다음 행동을 복원하는
단일 운영 기준이다. 제품 목적은 PRD, 기술 계약은 TRD, 검사 ID와 판정은
`docs/testing/PROJECT_GUARD_SPEC.md`를 따른다.

마지막 동기화 시각: `2026-07-23` (Asia/Seoul)

## 2. 현재 요약

- 저장소: `shindonghyun0516-a11y/FreshManager`
- 기준 `main` SHA: `be07b4bf37d5e0ad7c4ee65e7208f44c9b2b4ea3`
- 현재 Branch: `feat/issue-70-eg7-one-hour-pilot`
- 구현 Commit: `a648a2f18ce157957ddb9662b4e630479177ff00`
- Planning Issue #69: `OPEN`
- Implementation Issue #70: `OPEN`
- Draft PR #71: `OPEN · DRAFT`
- Merge: `NOT_MERGED`
- 현재 Engineering Gate: `EG-7 OFFLINE IMPLEMENTATION`
- EG-7 Live: `NOT_APPROVED`
- 실제 반복수집: `NOT_STARTED`
- 24시간 Scheduler: `NOT_IMPLEMENTED`
- ML 학습: `NOT_STARTED`

현재 작업은 Issue #69에서 PM이 승인한 첫 EG-7 5분·1시간 파일럿의 오프라인
Controller와 파생 인덱스를 Issue #70의 한 Branch·한 Draft PR로 구현하는 것이다.
실제 날짜·시각·할당량·운영 ID와 계획 지문은 생성하거나 확정하지 않는다.

## 3. Engineering Gate 상태

| Gate | 상태 | 근거 |
|---|---|---|
| EG-0 | PASS | 문서 기준선 승인 |
| EG-1 | PASS | 공식 121장소 CSV 읽기 전용 검증 |
| EG-2 | PASS | 공식 여의도 샘플 H-301~H-304 |
| EG-3 | PASS | Python Project Guard·CI |
| EG-4 | PASS | POI072 실제 단일 수집 |
| EG-5 | PASS | 대표 3 Area 실제 3/3 수집 |
| EG-6A | PASS | PR #52, 13개 Area·Spot·S-DoT 정적 패널 |
| EG-6B | PASS | 첫 실제 13 Area 13/13, 품질·백업·원격 동기화 확인과 Closeout |
| EG-7 | IMPLEMENTATION_IN_REVIEW | Issue #69 범위 승인, Issue #70 오프라인 구현; Live 미승인 |
| EG-8 | NOT_STARTED | 반복 관측 결과와 별도 PM 승인 필요 |
| Recommendation MVP | PLANNED | Gate number `NOT_ASSIGNED` |

EG-6B Closeout 이력:

- Issue #57: `CLOSED`
- Issue #67: `CLOSED`
- PR #68: `MERGED`
- 첫 실제 Batch: 승인된 13개 Area `13/13 SUCCESS`
- 첫 Batch 품질: `PASS`
- canonical Source/Backup 무결성: `PASS`
- PM 원격 동기화 확인: `COMPLETE`

이 완료 이력은 EG-7 Live 승인을 뜻하지 않는다.

## 4. EG-7 승인 구현 계약

### 4.1 시간·호출

- 시간대: `Asia/Seoul`
- Scheduling: 벽시계 5분 경계
- 길이: 1시간
- 계획 회차: 12
- 회차당 Area: 13
- 회차당 최대 호출: 13
- 전체 최대 호출: 156
- Area별 회차당 최대 호출: 1
- 재시도: 0
- 자동 재시도: 금지
- 지연 보충수집: 금지
- 중첩: 해당 회차 `SKIPPED_OVERLAP`, API 호출 0회

### 4.2 계획·식별자

- 한 파일럿에 하나의 `pilot_run_id`
- 정확히 12개의 계획 시각
- 회차별 사전 생성 canonical 소문자 UUIDv4 Batch ID
- 계획 canonical JSON의 결정적 SHA-256 지문
- Live 시작 뒤 계획 불변
- 건너뛴 ID는 `UNUSED`로 계획 이력에 남기고 다른 파일럿에서 재사용 금지

이 작업에서는 합성 테스트 ID만 임시 디렉터리에서 사용한다. 운영 ID·운영 계획은
생성하거나 예약하지 않는다.

### 4.3 실패·백업

- 개별 Area 실패: 재시도 없이 기록하고 기존 Collector 계약이 허용하면 다음 Area 진행
- 확정 공통 API·자격증명·스키마·할당량 오류: 현재 Batch 안전 중단, 남은 회차 중단
- 저장 오류: 기존 증거 보존, 남은 회차 중단
- Backup 오류: Source 보존, Collector·서울시 API 재호출 금지, 남은 회차 중단
- 적격 Batch는 Backup Worker를 최대 한 번 실행
- `LOCAL_SYNC_COPY_VERIFIED` 전에는 회차 성공으로 종결하지 않음

### 4.4 산출물

- 불변 JSON Pilot Plan
- append-only JSONL Execution Events
- 정확히 12행 Slot Index: CSV·JSONL
- 실제 시도 Area만 최대 156행 Area Observation Index: CSV·JSONL
- JSON Pilot Summary
- 중복 수집시각·API 관측시각·Raw SHA-256·Forecast 대상시각 집합을 별도 파생 플래그로 기록

Raw·Metadata·Collection Log·Manifest는 canonical 원본이다. EG-7 파생 산출물은
이를 대체·수정·삭제하지 않고 기존 Batch Manifest에도 추가하지 않는다.

## 5. Live 차단 상태

다음 결정은 모두 OPEN이다.

- 실제 파일럿 날짜
- 실제 시작시각
- 확인된 API 할당량
- 운영 `pilot_run_id`
- 운영 12개 Batch ID
- 운영 계획 지문
- 명시적 PM Live 승인
- 24시간 확대

기본값:

```text
quota_confirmation_status=UNCONFIRMED
live_approval_status=NOT_APPROVED
```

둘 중 하나라도 기본 차단 상태이거나 승인 지문·현재 시간창·Area 계약·호출상한·
환경·Lock·ID 충돌 검사가 맞지 않으면 Live를 거부한다.

## 6. 명시적 제외 범위

- 실제 서울시 API 호출
- 실제 Collector 실행
- 실제 Backup Worker 실행
- Google Drive 접근
- S-DoT 동적 수집
- Spot 평가
- Recommendation
- ML 학습·성능평가
- 24시간 Scheduler
- cron·launchd·영구 백그라운드 서비스
- 자동 재시도
- 일반 Raw-to-CSV Exporter
- 121개 Area 확대

정적 S-DoT 연결은 기존 참조 Context로만 유지한다. Spot 후보는 계속
`field_verified=false`이며 Area 데이터만으로 Spot 추천을 만들지 않는다.

## 7. 구현 파일 범위

| 파일 | 역할 |
|---|---|
| `freshmanager/eg7.py` | 계획·지문·Live Gate·벽시계 회차·Lock·Collector/Backup 조립·사건로그·파생 출력 |
| `tests/test_eg7.py` | 계획·Scheduling·Lock·실패·인덱스·Dry-run 합성 테스트 |
| `scripts/project_guard_check.py` | H-707 오프라인 반복주기 계약 활성화 |
| `tests/test_project_guard_check.py` | H-707 PASS·회귀·47개 집계 검증 |
| `README.md` | 운영자용 EG-7 범위·Dry-run·Live 차단 안내 |
| `docs/testing/PROJECT_GUARD_SPEC.md` | H-707 입력·PASS·FAIL·활성 상태 |
| `docs/testing/QUALITY_GATES.md` | EG-7 구현·실제 파일럿 통과조건 분리 |
| `docs/engineering/FreshManager_TRD_v1.0.md` | Controller와 파생 인덱스 기술 구조 |
| `docs/rules/DATA_COLLECTION_RULES.md` | 5분·무보충·실패·중복 보존 규칙 |
| `docs/data/FIELD_DICTIONARY.md` | 계획·사건·Slot/Area Index·Summary 필드 |
| `ai-context/DECISION_LOG.md` | PM 승인 결정 D-012 |
| `ai-context/ARCHITECTURE_DECISIONS.md` | 구조 결정 ADR-008 |
| `PROJECT_STATUS.md` | 현재 Issue·Branch·PR·검증·다음 행동 |

## 8. 검증 상태

현재 로컬 최종검증:

- EG-7 Target Tests: `24/24 PASS`
- Full Unit Tests: `345/345 PASS`
- Project Guard: `PASS 43 / FAIL 0 / WARN 0 / SKIP 4 / TOTAL 47`
- H-706: `PASS`
- H-707: `PASS`
- H-708: `PASS`
- Markdown 구조·코드 블록: `PASS`
- `git diff --check`: `PASS`
- 서울시 API 호출: `0`
- S-DoT API 호출: `0`
- 운영 Collector 실행: `0`
- 운영 Backup 실행: `0`
- 운영 Batch 접근: `0`
- Google Drive 접근: `0`
- 운영 Batch ID 생성·예약: `0`
- 기존 운영 증거 변경: `0`
- 기존 Fake 증거 변경: `0`

GitHub CI는 Push마다 새 HEAD로 다시 실행되므로 고정 상태를 이 문서에 복제하지 않고
Draft PR #71의 현재 Check를 읽기 전용으로 확인한다.
H-707은 구현과 함께 `PASS`로 활성화됐지만
이는 합성 계약 검사이며 실제 할당량·
운영 계획·PM Live 승인 완료를 의미하지 않는다.

## 9. GitHub 상태

- Issue #69: 승인 범위의 Planning Issue, 계속 `OPEN`
- Issue #70: 구현 Issue, 계속 `OPEN`
- Branch: `feat/issue-70-eg7-one-hour-pilot`
- Draft PR #71: `OPEN · DRAFT`, target `main`
- Ready 전환: 금지
- Merge: 금지
- 두 Issue Close: 금지

## 10. 다음 행동

1. Draft PR #71의 현재 HEAD와 CI를 확인하고 독립 검토를 요청한다.
2. Issue #69와 #70은 열린 상태로 유지한다.
3. Ready 전환·Merge·Live 실행 없이 중단한다.

## 11. 새 세션 복원 메모

새 세션은 `AGENTS.md` → 이 문서 → `ai-context/PROJECT_MEMORY.md` → PRD → TRD →
Issue #69·#70과 Draft PR → 현재 Diff → 관련 Rule·Quality·Data 문서 → Decision
Log·ADR 순서로 읽는다.

EG-7 H-707 PASS와 코드 구현을 실제 파일럿 성공으로 해석하지 않는다. 실제 운영
계획을 생성하거나 서울시 API를 호출하려면 PM의 새로운 명시적 승인이 필요하다.
