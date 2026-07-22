# Cloud Backup and CSV Management Plan

- 문서 상태: `PLANNED` · PM 결정 반영·Diff 재검토 대기
- 적용 프로젝트: FreshManager Data PoC
- 기준일: 2026-07-22
- 공식 클라우드 제공자: Google Drive
- 현재 구현 상태: Backup Worker·CSV Exporter 모두 `NOT_IMPLEMENTED`
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 FreshManager의 로컬 수집 원본을 Batch 완료 직후 Google Drive에 검증된
복사본으로 백업하고, 첫 실제 Batch의 구조를 확인한 뒤 조회·분석용 CSV를 도입하는
목표 계약을 정의한다. Collector 실행, 백업, 원격 동기화와 CSV 생성을 서로 다른
책임으로 분리해 백업이나 파생자료 실패가 서울시 API 재호출로 이어지지 않게 한다.

이 문서의 파일명은 특정 제공자에 종속되지 않지만, 현재 PM이 선택한 공식 제공자는
Google Drive다. iCloud Drive와 수동 백업은 현행 운영방식으로 사용하지 않는다.

## 2. 적용범위

포함하는 목표 범위:

- 완료된 EG-6B·EG-7 Batch의 Google Drive 자동 백업
- Google Drive for Desktop Sync 로컬 동기화 폴더 사용
- Batch 완료 후 별도 1회 실행형 Backup Worker 즉시 실행
- Manifest 기반 파일 수·SHA-256 검증과 백업 상태·Receipt
- 일일 무결성 감사, 복원 시험과 보존기간 결정
- 첫 실제 Batch 이후 Raw-to-CSV Exporter 도입 순서

현재 제외 범위:

- Google Drive API, OAuth와 Google Drive SDK
- 클라우드에서 서울시 API 수집 실행
- Backup Worker·CSV Exporter의 이번 문서 작업 내 구현
- 실제 Google Drive 폴더·파일 생성과 실제 데이터 복사
- EG-7 반복수집 구현, 추천 모델과 판매효과 분석

## 3. 현재 구현 상태

| 항목 | 현재 상태 |
|---|---|
| EG-6B Collector | 구현·오프라인 검증·`main` 병합 완료 |
| EG-6B 실제 13개 Area Batch | 미실행 |
| env-file·output-root Probe | PASS |
| Google Drive 공식 제공자 선택 | PM 결정 완료 |
| Google Drive for Desktop Sync 설치·로그인 | 확인 필요; 계정 이메일 기록 금지 |
| Backup Root | 논리 루트 `FreshManager-Data/` 승인; 실제 동기화 절대경로는 저장소에 기록하지 않음 |
| Backup Worker | `NOT_IMPLEMENTED` |
| 백업 Receipt·일일 감사·복원시험 | `NOT_IMPLEMENTED` |
| Raw-to-CSV Exporter | `NOT_IMPLEMENTED` |

자동 백업을 문서화한 사실은 구현·운영 완료를 의미하지 않는다. Google Drive
실제 계정 이메일이나 동기화 절대경로를 저장소·Receipt·로그에 기록하지 않는다.

## 4. 목표 운영 상태

```text
로컬 EG-6B·EG-7 Collector
→ 불변 Raw·Metadata·Collection Log·Manifest
→ 완료 Batch 판정
→ 완료 직후 1회 실행형 Backup Worker 호출
→ Google Drive for Desktop Sync 로컬 동기화 폴더의 임시 디렉터리
→ 파일 수·Manifest SHA-256 검증
→ 원자적 Batch 게시
→ LOCAL_CLOUD_COPY_VERIFIED
→ Google Drive 데스크톱 앱 동기화
→ 별도 원격 업로드 확인
→ REMOTE_SYNC_CONFIRMED
```

Collector는 수집과 로컬 원본 생성만 담당한다. 별도 실행 조정 계층은 Batch가
완결된 직후 1회 실행형 Backup Worker를 호출한다. Worker는 완료 Batch를 검증·
복사하고 상태와 Receipt를 남긴다. Google Drive for Desktop Sync는 로컬 동기화
폴더에서 원격 Google Drive로 업로드한다.

## 5. 로컬 원본과 Google Drive 복사본

- 로컬 Raw JSON·요청별 Metadata·Collection Log·Manifest가 공식 원본이다.
- Google Drive 파일은 공식 원본의 검증된 복사본이다.
- 백업 성공 후에도 로컬 원본을 삭제·수정·이동하거나 덮어쓰지 않는다.
- 백업 복사본이 원본보다 상위 기준이 되거나 Manifest를 다시 정의하지 않는다.
- Raw와 파생 CSV를 같은 원본 등급으로 표현하지 않는다.

## 6. Google Drive for Desktop Sync 사용 원칙

공식 방식은 Google Drive API가 아니라 Google Drive for Desktop Sync의 로컬
동기화 폴더에 파일을 복사하는 것이다. 이유는 다음과 같다.

- 현재 1인 로컬 운영 구조를 유지할 수 있다.
- API 자격증명·OAuth 토큰·SDK라는 새 비밀정보와 의존성을 추가하지 않는다.
- 파일 복사와 원격 업로드 책임을 분리할 수 있다.
- 표준 파일시스템 연산과 Manifest 검증을 재사용할 수 있다.

Google Drive API·OAuth·SDK는 제외 범위이며 구현하지 않는다.
로컬 동기화 폴더에 복사된 사실만으로 원격 업로드 완료를 주장하지 않는다.

## 7. Backup Root 논리 계약

저장소 문서가 정의하는 Backup Root는 다음 논리 구조뿐이다.

```text
FreshManager-Data/
├── 01_raw-backup/
│   └── eg6b-single-13/
├── 02_spreadsheet/
│   ├── current/
│   └── snapshots/
└── 03_reference/
```

실제 Google Drive for Desktop Sync 계정 이메일과 로컬 동기화 절대경로는 저장소,
Receipt와 운영 로그에 기록하지 않는다. 실행 시점에는 승인된 로컬 설정을 통해
논리 루트가 접근 가능하고 쓰기 가능한지만 Preflight Boolean으로 확인한다. 계정
이메일·경로 문자열·일부 문자·해시는 출력하지 않는다.

`.env`, API Key, 인증 URL과 저장소 전체는 동기화 대상에서 제외한다.

## 8. Collector·Backup Worker·Desktop Sync 책임

| 구성요소 | 책임 | 책임이 아닌 것 |
|---|---|---|
| EG-6B·EG-7 Collector | 승인 Area 호출, 로컬 불변 산출물과 Manifest 생성 | 클라우드 복사·원격 업로드·백업 재시도 |
| Batch 실행 조정 계층 | Batch 완료 판정 직후 1회 실행형 Worker 호출 | Collector 내부 백업·주기 Scheduler |
| Backup Worker | 완료 Batch 검증, 복사, 충돌 처리, Receipt 기록 | 서울시 API 호출·Raw 수정·Google Drive API 호출 |
| Google Drive for Desktop Sync | 로컬 동기화 폴더를 원격 Drive에 동기화 | Manifest 의미·수집 성공·백업 무결성 판정 |

Backup Worker는 한 번 실행해 당시의 백업 대상 Batch를 처리하고 종료하는 구조를
우선 적용한다. 장기 상주 프로세스와 자체 Scheduler는 현재 목표가 아니다.

## 9. 즉시 백업 정책

Backup Worker는 Batch의 Collection Log·Manifest 게시와 무결성 검증이 끝난 직후
한 번 호출한다. 시간 간격 기반 폴링이나 30분 주기는 사용하지 않는다.

- 종료코드 `0`과 증거가 완결된 종료코드 `1` Batch를 즉시 백업 대상으로 삼는다.
- 증거가 불완전한 종료코드 `2` Batch는 자동 백업하지 않는다.
- Worker 실패는 Receipt에 기록하고 서울시 API를 재호출하지 않는다.
- 같은 `batch_id`를 덮어쓰지 않으며, 재실행은 별도 승인된 백업 재시도일 뿐 수집 재실행이 아니다.

## 10. 완료 Batch 판정과 부분 실패

백업 가능한 Batch는 다음을 모두 만족해야 한다.

1. Collector 실행이 종료됐다.
2. `collection_log.json`과 `manifest.json`이 존재한다.
3. Manifest가 참조하는 Raw·Metadata·Collection Log가 모두 존재한다.
4. 파일 수·크기·SHA-256 검증이 통과한다.
5. 임시·partial 파일이 대상에 포함되지 않는다.
6. 같은 `batch_id`가 아직 처리 중이 아니다.

종료코드 `1`인 부분 실패 Batch도 회차 증거가 완결되고 Manifest 검증이 통과하면
백업한다. 실패 Area와 정상 Area를 포함한 회차 전체를 보존해야 하기 때문이다.
공통 오류로 증거가 불완전하거나 실행 중인 Batch는 백업하지 않는다.

## 11. 안전한 복사와 원자적 게시

1. Google Drive for Desktop Sync에 연결된 논리 루트 `FreshManager-Data/01_raw-backup/eg6b-single-13/` 아래 같은 파일시스템의 임시 Batch 디렉터리를 만든다.
2. Raw·Metadata·Collection Log·Manifest를 함께 복사한다.
3. 원본과 복사본의 파일 수를 비교한다.
4. Manifest 기준 크기·SHA-256을 복사본에서 재검증한다.
5. 검증이 통과한 경우에만 임시 디렉터리를 최종 `batch_id` 경로로 원자적으로 게시한다.
6. 실패하면 최종 정상 경로를 만들지 않고 상태와 비민감 오류만 기록한다.

동일 `batch_id` 최종 경로를 덮어쓰지 않는다.

- 파일 수와 모든 해시가 같으면 이미 게시된 동일 복사본으로 판정하고 중복 복사를 생략한다.
- 하나라도 다르면 `CONFLICT`로 중단하고 기존 복사본과 로컬 원본을 수정하지 않는다.
- 충돌을 해결하기 위해 서울시 API를 다시 호출하지 않는다.

## 12. Manifest 검증과 Secret 제외

백업 검증의 기준은 Collector가 생성한 Manifest다. Backup Worker가 임의의 새 원본
해시 계약을 만들지 않는다. 최소 검증은 다음과 같다.

- Manifest가 참조하는 상대경로의 root 이탈 금지
- 파일 수·크기·SHA-256 일치
- Raw·Metadata·Collection Log·Manifest 함께 보존
- `.env`, API Key, 인증 URL, 임시·partial·Probe 파일 제외
- 실제 Raw 전문과 사용자 절대경로의 운영 로그 출력 금지

백업 실패와 CSV 생성 실패는 모두 서울시 API 재호출 사유가 아니다.

## 13. 백업 상태 모델

아래 상태는 모두 `FUTURE_CONTRACT`이며 현재 코드에 구현되지 않았다.

| 상태 | 의미 | 주요 전이조건 |
|---|---|---|
| `PENDING` | 완료 Batch가 백업 대기 중 | 완료 Batch·Manifest 검증 대상 확인 |
| `IN_PROGRESS` | 단일 Worker가 임시 경로로 복사·검증 중 | Worker가 배타적으로 Batch 처리 시작 |
| `LOCAL_CLOUD_COPY_VERIFIED` | 로컬 Google Drive 동기화 폴더의 복사본 파일 수·해시 검증 완료 | 원자적 게시 완료 |
| `REMOTE_SYNC_PENDING` | 로컬 복사 검증은 끝났으나 원격 업로드 완료는 미확인 | Drive desktop 동기화 대기 또는 확인 불가 |
| `REMOTE_SYNC_CONFIRMED` | 실제 Google Drive 원격 공간에서 업로드 완료 확인 | 승인된 원격 확인방식으로 완료 증거 확보 |
| `FAILED` | 복사·검증·상태 확인 중 복구 가능한 실패 | 오류 기록 후 다음 승인된 Worker 실행에서 재검토 |
| `CONFLICT` | 동일 `batch_id` 복사본과 원본의 파일 수·해시가 다름 | 자동 덮어쓰기 없이 PM 판단 대기 |

허용 전이의 기본 흐름:

```text
PENDING
→ IN_PROGRESS
→ LOCAL_CLOUD_COPY_VERIFIED
→ REMOTE_SYNC_PENDING
→ REMOTE_SYNC_CONFIRMED
```

`IN_PROGRESS`에서 복사·검증 실패 시 `FAILED`, 동일 `batch_id` 불일치 시
`CONFLICT`로 전이한다. `LOCAL_CLOUD_COPY_VERIFIED`만으로
`REMOTE_SYNC_CONFIRMED`를 기록하지 않는다.

## 14. 백업 Receipt와 운영 감사 목표

Backup Worker는 향후 Batch별 Receipt를 남기는 것을 목표로 한다. 정확한 저장 형식은
구현 Issue에서 승인한다. Receipt 후보 정보는 다음과 같다.

- `backup_attempt_id`, `batch_id`, 상태
- 시작·종료시각
- 비민감 목적지 식별자
- 대상·복사·검증 파일 수
- Manifest 검증 결과
- 원격 동기화 확인 결과와 확인시각
- 충돌·실패 유형
- Worker 버전

Receipt와 로그에는 Google 계정 이메일, 실제 동기화 절대경로와 사용자 식별정보를
기록하지 않는다. 목적지는 `FreshManager-Data` 아래의 비민감 논리 식별자로만 남긴다.

일일 무결성 감사는 완료 백업의 파일 수와 Manifest SHA-256을 다시 확인하는 목표다.
복원 시험은 선택한 Batch를 새 로컬 경로에 복원하고 Manifest·JSON 파싱을 검증하는
목표다. 원본 경로 위로 복원하지 않는다.

다음 항목은 PM 결정 전이다.

- 일일 감사의 정확한 실행시각·표본 또는 전체 범위
- 복원시험 주기와 표본 선정
- 로컬 원본·Google Drive 복사본·CSV·Receipt 보존기간
- 오래된 자료의 삭제 승인과 절차

## 15. CSV 후속 도입계획

CSV는 첫 실제 EG-6B Batch 전에 구현하지 않는다. 순서는 다음과 같다.

1. 첫 EG-6B Live Batch 확보
2. Raw·Metadata·Manifest 데이터 품질 감사
3. 실제 필드·결측·Forecast 구조 확인
4. CSV 데이터 계약 정의
5. Raw-to-CSV Exporter 별도 Issue
6. Exporter 구현·테스트·PR·`main` 병합
7. 첫 Batch CSV 생성
8. 논리 루트 `FreshManager-Data/02_spreadsheet/` 반영
9. PM 가독성·필터·중복 검수
10. EG-7 전 누적·재생성 계약 검증

예정 CSV:

| 파일 | 역할 | 기본 식별키 후보 |
|---|---|---|
| `batches.csv` | 회차·성공·실패·무결성 요약 | `batch_id` |
| `area_observations.csv` | Area 현재 관측값 | `area_code + population_reference_time + request_id` |
| `area_forecasts.csv` | 수집시점별 미래 예측 | `area_code + forecast_snapshot_time + forecast_target_time + request_id` |
| `collection_errors.csv` | 요청·Area별 오류 | `request_id + area_code` |

- Raw JSON과 수집 증거가 공식 원본이다.
- CSV는 조회·정렬·필터·분석용 파생자료이며 Raw에서 재생성할 수 있어야 한다.
- CSV 실패로 서울시 API를 재호출하지 않는다.
- Area 관측값과 S-DoT 관측·Spot Candidate Context를 같은 측정값으로 혼합하지 않는다.
- 시스템 생성 CSV와 PM의 수동 메모 시트를 분리한다.

## 16. 단계별 구현·운영 순서

```text
Google Drive for Desktop Sync 백업 계획 문서화
→ Desktop Sync 설치·로그인과 논리 루트 접근 가능 여부 확인
→ Backup Worker 구현
→ Fake Batch 백업 검증
→ Backup Worker PR·CI·main 병합
→ EG-6B Live 최종 Preflight 재검증
→ PM 최대 13회 실제 호출 승인
→ 첫 13개 Area 실제 Batch
→ 로컬 원본·Manifest 검증
→ Batch 완료 직후 Backup Worker 1회 실행
→ 복사본 파일 수·SHA-256 검증
→ PM 데이터 품질 감사와 EG-6B PASS·보완 판정
→ 첫 Batch 기반 CSV 계약·Exporter 별도 작업
→ EG-7 반복수집 진입 검토
```

EG-6C는 공식 Engineering Gate로 신설하지 않는다. Backup Worker와 CSV Exporter는
EG-6B Live·EG-7 사이의 명시적 선행 작업이지만 새 EG 번호가 아니다.

## 17. 미결정사항

- Google Drive for Desktop Sync 설치·로그인 상태
- 논리 루트 접근·쓰기 가능 여부를 값 비노출 Boolean으로 확인하는 방법
- Google Drive와 로컬 디스크 잔여 용량
- 파일 스트리밍 또는 미러링 방식
- 원격 동기화 완료 확인방식
- Worker 중복 실행 잠금과 stale 상태 복구
- 백업·Receipt 보존기간
- 일일 무결성 감사와 복원시험 주기
- CSV 세부 스키마·인코딩·원자적 게시 방식

## 18. 완료조건

문서 계획 완료조건:

- 현재 구현과 목표 계약이 구분돼 있다.
- Google Drive가 공식 제공자이고 iCloud·수동 백업이 현행 운영방식이 아님을 명시한다.
- 실제 계정 이메일·동기화 절대경로는 기록하지 않고 `FreshManager-Data` 논리 구조만 정의한다.
- Collector·Worker·Desktop Sync 책임이 분리돼 있다.
- 상태, 충돌, 무결성, Secret 제외와 원격 확인 차이가 정의돼 있다.
- CSV가 첫 Batch 이후의 파생자료로 정의돼 있다.

운영 준비 완료조건은 별도 구현 Issue에서 다음을 모두 검증해야 한다.

- Desktop Sync의 논리 루트 접근 가능성 확인(계정 이메일·절대경로 비기록)
- Backup Worker Fake Batch 정상·부분 실패·중복·충돌·오류 테스트
- 임시 복사·검증·원자적 게시와 Receipt
- Batch 완료 직후 단일 Worker 호출·중복 실행 방지 검증
- Google Drive 원격 동기화 확인방식
- Project Guard·Unit Tests·CI·PM Merge 승인
- EG-6B Live Preflight 재통과와 별도 실제 호출 승인
