# 데이터 수집 실행 가이드 (비개발자용)

> **현행 상태**  PoC의 13개 Area 5분 반복수집 Runtime은 Google Apps Script다(`ACTIVE`).
> Apps Script는 공식 POI 코드로 서울시 API를 호출하며, 사용자의 로컬 Python 프로세스나
> Codex·Claude Code 세션과 분리돼 그 종료 여부와 무관하게 동작한다. 이전 버전의 이 문서가
> "Apps Script는 폐기됐다"고 적었던 표현은 `ai-context/DECISION_LOG.md`의 새 결정으로
> SUPERSEDED됐다. 로컬 Python(EG-6B·EG-7)은 상시 수집 Runtime이 아니라 기술검증·Pilot
> Runner로 유지하며, 이 문서의 4~7절이 다루는 EG-6B 단일 회차 실행 절차는 그 검증 목적
> 그대로 유효하다. Python은 이후 정규화·분석·머신러닝에 사용한다. PM이 Google Apps
> Script 화면에서 직접 확인한 결과 5분 시간 기반 Trigger가 `collectData`를 반복
> 실행하며 13개 Area 데이터가 계속 누적되고 있다 — 5분 자동수집 동작은 `ACTIVE`다.
> 다만 이는 24시간 이상 장기 무중단 지속성 검증과는 다른 사실이며, 그 검증은 아직
> `NOT_COMPLETED`다. Apps Script 소스의 Git 버전관리와 Python 쪽 데이터 통합은
> `PLANNED`다. 수집과 분리된 Google Drive for Desktop Sync Backup Worker 구현은
> 완료됐으며, EG-7 Live 반복수집은 아직 실행되지 않았다.

## 0. 현재 Apps Script 자동수집 절차 (참고용)

1. Apps Script 시간 기반 Trigger가 `collectData`를 5분마다 자동 실행한다.
2. 승인된 13개 공식 POI 코드를 순차 호출한다(Area 이름 아님).
3. `raw_log_v3`에 Area별 Raw 응답과 상태를 저장한다.
4. `population_current_v3`에 현재 인구를 저장한다.
5. `population_forecast_v3`에 Forecast를 저장한다.
6. Python은 이후 정규화·분석·머신러닝에 사용한다.

한 번의 정상 실행은 `raw_log_v3` 13건, `population_current_v3` 13건,
`population_forecast_v3` 156건을 만들고, 실행마다 서로 다른
`collection_run_id`를 사용한다. 이 문서에는 실제 Spreadsheet URL, Apps Script
프로젝트 URL, Google 계정 이메일, 실제 API Key, Script Property 값, 로컬
절대경로를 기록하지 않는다.

## 1. 먼저 확인할 공식 문서

1. [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md) — 지금 어디까지 진행됐는지
2. [`FreshManager_PRD_v1.0.md`](../product/FreshManager_PRD_v1.0.md) — 무엇을 왜 검증하는지
3. [`FreshManager_TRD_v1.0.md`](../engineering/FreshManager_TRD_v1.0.md) — 현재 수집기가 어떻게 동작하는지
4. [`DATA_COLLECTION_RULES.md`](../rules/DATA_COLLECTION_RULES.md) — 원본·메타데이터·백업 규칙
5. [`QUALITY_GATES.md`](../testing/QUALITY_GATES.md) — 다음 단계로 넘어가는 조건
6. [`CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`](CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md) — Google Drive 백업과 CSV 후속 계획

## 2. 현재 단계

- EG-4 여의도 실제 단일 수집: 완료
- EG-5 대표 3개 Area 실제 수집: 완료
- EG-6A 13개 Area·Spot·S-DoT 패널: 확정·`main` 반영 완료
- EG-6B 13개 Area 단일 회차 파이프라인: 구현·오프라인 검증·`main` 병합 완료
- EG-6B 실제 13개 Area 단일 회차: 완료(13/13 SUCCESS, 품질 PASS, 원격 동기화
  COMPLETE — 상세는 `PROJECT_STATUS.md` §2 참조)
- Issue #57 env-file·output-root Probe: PASS
- Google Drive 자동 백업: `FreshManager-Data/` 논리 루트 승인, Backup Worker
  구현 완료(Issue #60·PR #61, H-708 PASS)
- EG-7 반복수집 구현: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #71 병합, Issue
  #70 종료). Live pilot: `NOT_STARTED`(1시간·12회차, 실제 호출 0회)

PR #54 병합 당시에는 그 자체가 실제 호출 승인이 아니었으며, PM이 EG-6B
PASS를 판정하기 전에는 반복수집으로 넘어가지 않는 것이 승인 조건이었다.
이후 EG-6B는 실제 13개 Area 13/13 SUCCESS·품질 PASS를 완료했고(위 참조),
EG-7 구현도 `main`에 반영됐다. EG-7 Live pilot은 아직 `NOT_STARTED`다.

## 3. 일반 검증

다음 명령은 실제 서울시 API를 호출하지 않는다.

```bash
python3 scripts/project_guard_check.py
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

정상 기준은 Project Guard `FAIL=0`, `WARN=0`, 종료 코드 `0`과 전체 Unit Tests
PASS다. 검증 수는 코드 변경에 따라 달라질 수 있으므로 숫자만 보고 성공으로 판단하지
않고 실패 항목이 없는지 함께 확인한다.

## 4. 실제 EG-6B 실행 전 승인사항

PM이 다음을 모두 명시적으로 승인해야 한다.

- Google Drive for Desktop Sync 설치·로그인과 논리 루트 접근 가능 여부
- 실제 계정 이메일·동기화 절대경로 비기록 확인
- Backup Worker Fake Batch·완료 직후 호출 검증·PR·CI·`main` 병합
- Live 직전 Preflight 재통과
- 현재 `main` HEAD와 깨끗한 Working Tree
- 정확한 로컬 env-file 경로
- 저장소 밖의 정확한 output-root
- 고정 13개 Area와 총 최대 13회 호출
- timeout과 실행 시각
- 실제 결과 검토 방법

환경변수 값, API Key 일부 문자·길이, 인증 URL과 Raw 응답 전문을 화면이나 보고서에
출력하지 않는다. `.env`를 Git에 추가하거나 다른 위치로 복사하지 않는다.

## 5. 공식 실행 명령 형식

다음은 형식 확인용이다. 자리표시자를 임의 경로로 바꾸거나 PM 승인 전에 실행하지 않는다.

```bash
python3 -m freshmanager.eg6b \
  --env-file /path/to/approved-local.env \
  --output-root /path/to/approved-external-output-root \
  --timeout 10 \
  --execute-live
```

`--execute-live`는 기술적 실행 확인 옵션일 뿐 PM 승인을 대신하지 않는다.

## 6. 실행 후 확인사항

- 대상 Area 13개
- Area별 최대 1회, 총 최대 13회
- 자동 재시도 0회
- 성공 수·실패 수·실패 Area 목록
- Raw JSON과 요청별 Metadata 분리 저장
- Collection Log와 Manifest 생성
- 참조파일·산출물 SHA-256 검증
- 성공한 Area 결과 보존
- 기존 결과 자동 삭제·덮어쓰기 없음

실행 결과가 생성됐다는 사실만으로 EG-6B를 PASS 처리하지 않는다. PM이 위 증거를
검토해 PASS 또는 보완을 결정한다.

## 7. 반복수집 전 필수 Gate (EG-6B/EG-7 로컬 검증 기준)

이 절은 로컬 Python(EG-6B·EG-7) 기술검증 경로에 적용된다. 상시 반복수집
자체는 이제 Apps Script Runtime이 담당하므로, 아래 Gate는 "로컬에서 검증을
반복 실행할 때"의 기준이며 상시운영 승인 절차가 아니다.

공식 백업 방식은 Google Drive for Desktop Sync다. iCloud와 수동 백업은 현행
운영방식으로 사용하지 않는다. 로컬 EG-6B/EG-7 실행은 1회 실행형
Backup Worker가 Batch 완료 직후 `FreshManager-Data/` 논리 루트로 복사·검증한다.
실제 계정 이메일과 동기화 절대경로는 기록하지 않으며 Google Drive API·OAuth·SDK는
구현하지 않는다. 원격 동기화 확인과 보존·복원 정책은 PM이 별도로 승인한다.
승인 없는 수집 Scheduler 신설과 121개 Area 확대는 여전히 현행 절차가 아니다.
EG-6C도 신설하지 않는다.

Apps Script Runtime의 API Key는 `.env`가 아니라 Apps Script Script Properties에
`SEOUL_OPEN_API_KEY`라는 같은 변수명으로 별도 저장한다. 두 환경은 자동으로
연결되지 않으며, Spreadsheet URL·Apps Script 프로젝트 URL·Google 계정 이메일·
Script Property 값은 이 저장소의 어떤 문서에도 기록하지 않는다.

첫 실제 Batch가 품질 감사를 통과한 뒤에만 Raw-to-CSV Exporter를 별도 Issue에서
검토한다. CSV 실패는 API 재호출 사유가 아니며 Raw JSON이 공식 원본이다.

## 8. EG-8A v3 source sheets 수동 CSV Export 절차

> **목적**  EG-8A Loader V0 검증을 위한 읽기 전용 Snapshot을 확보한다. 이
> 절차는 `docs/data/ML_READY_DATASET_SPEC.md` §3.1이 확정한 V0 입력 방식
> (수동 Spreadsheet CSV Export)의 실행 절차를 소유한다.

### 8.1 대상 시트

1. `raw_log_v3`
2. `population_current_v3`
3. `population_forecast_v3`

### 8.2 Export 체크리스트

시트마다 다음을 확인하며 CSV로 Export한다.

- [ ] 시트별 CSV 1개
- [ ] 첫 Header 행 유지
- [ ] 컬럼명 변경 금지
- [ ] 컬럼 순서 변경 금지
- [ ] 행 필터링 금지
- [ ] 수식이 있다면 Export 결과값 기준으로 저장
- [ ] 날짜·시간 형식 임의 변환 금지
- [ ] 빈 값 채우기 금지
- [ ] 숫자 단위 또는 기호 추가 금지
- [ ] Excel에서 열고 다시 저장하지 않음(UTF-8 CSV 상태 유지)
- [ ] 실제 API Key·계정정보·URL이 포함되지 않았는지 확인

### 8.3 파일명

```text
raw_log_v3.csv
population_current_v3.csv
population_forecast_v3.csv
```

### 8.4 Export 범위

전체 누적 데이터 Export를 우선한다. 현실적으로 어려우면 다음 최소 조건을
모두 만족하는 샘플로 대신할 수 있다 — 단 사용 여부는 PM이 직접 확인한 뒤
결정한다.

- [ ] 서로 다른 `collection_run_id` 2개 이상
- [ ] 각 Run에 13개 Area 전체 포함
- [ ] Current Population 전체 행 포함
- [ ] Forecast의 모든 Target 행 포함
- [ ] Header 포함

### 8.5 저장 위치

Git에 Commit하지 않는다. 저장 위치 후보와 최종 승인은
`docs/data/ML_READY_DATASET_SPEC.md` §12.1을 따르며, 이 문서는 구체 경로를
중복 기록하지 않는다.

### 8.6 Export 이후

Export한 CSV를 PM이 확인한 뒤에만 EG-8A 구현 Issue(Source
Reader·Schema/Normalization)를 시작한다. 확보 전에는 구현 Issue를 열지
않는다.
