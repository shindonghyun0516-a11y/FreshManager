# FreshManager Repository Readiness Audit

- 문서 상태: `APPROVED_AUDIT_BASELINE`
- 관련 Issue: #144
- 기준 Repository: `shindonghyun0516-a11y/FreshManager`
- 기준 main SHA: `b87d7cb03f860856888766da56bf904e8f649769`
- 기준일: 2026-07-31 (Asia/Seoul)
- PM Decision: `APPROVED_WITH_INTERVIEW_EVIDENCE_CORRECTION`

이 보고서는 Vue·FastAPI 기반 Area-first 웹 파일럿 구현 전 Git 추적 자산의 현재
역할과 준비도를 분류한다. PM은 분류를 승인했지만 기존 파일의 수정·이동·삭제 또는
구현 실행은 이 Audit 시점에는 승인하지 않았다. 아래 분류와 `PENDING`은 Issue #144
기준의 역사적 감사결과다.

## Issue #150 사후 실행상태

Issue #150의 별도 PM 승인에 따라 문서 이동 4건과 History 보관 5건을 현재 Draft에
반영했다. 아래 Inventory의 경로는 이동 후 경로로 정렬했지만, 분류값은 당시
Audit의 판단근거를 보존한다. 이 Draft가 병합되기 전 실행상태는
`DRAFT_PENDING_PM_REVIEW`다.

- 문서 이동 4건: `MOVED_IN_ISSUE_150_DRAFT`
- History 보관 5건: `ARCHIVED_IN_ISSUE_150_DRAFT`
- `data/reference/pilot_spot_options.csv`: `MOVE_CANDIDATE` 유지, 이번 범위에서 미이동
- 파일 삭제: 0건

## PM 승인 범위

| Classification | 승인 의미 |
|---|---|
| `KEEP` | 현재 유지 승인 |
| `MOVE_CANDIDATE` | 이동 후보로 승인, 이동 실행 미승인 |
| `UPDATE_REQUIRED` | 갱신 후보로 승인, 수정 실행 미승인 |
| `ARCHIVE_CANDIDATE` | 보관 후보로 승인, 이동 실행 미승인 |
| `DELETE_CANDIDATE=0` | 현재 삭제작업을 만들지 않음 |

Inventory 각 행의 `PM Decision=PENDING`은 해당 파일의 실제 이동·수정·보관 실행이
아직 승인되지 않았다는 뜻이다.

### 실제 인터뷰와 Repository Evidence

| 항목 | 상태 |
|---|---|
| `actual_interview_execution_status` | `PM_CONFIRMED` |
| `repository_evidence_status` | `NOT_TRACKED` |
| `synthetic_matrix_status` | `NOT_ACTUAL_INTERVIEW_EVIDENCE` |
| `gate_c_status` | `SEPARATE_EVALUATION_REQUIRED` |

실제 프래시매니저 인터뷰 수행 사실은 PM이 확인했다. 다만 Git 추적자산에는 실제
인터뷰 원문·요약·참여기록 또는 개인정보 없는 외부 증거 참조가 없어 정본 간
Evidence Traceability가 부족하다. `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md`는 공개자료 기반
합성자료이며 실제 인터뷰, 실제 직접 인용 또는 Gate C 통과 근거가 아니다. 실제
인터뷰 수행 사실만으로 Gate C 통과를 판정하지 않는다.

후속 문서 정합화는 실제 인터뷰 수행 표현을 유지하면서, 별도 PM 승인 아래 개인정보
없는 Evidence Summary, 참여자 식별정보 없는 최소 Metadata, 실제 답변과 해석의
구분, 합성 Matrix와 실제 인터뷰의 분리, Gate C 상태의 별도 기록 중 필요한 최소
범위만 다룬다. 개인정보·원본 녹취·참여자 식별정보는 Git에 추가하지 않는다.

## 1. Executive Summary

기준 main의 Git 추적 파일은 102개다. 전체 파일을 코드·테스트·문서·데이터·설정·
Workflow 관점에서 확인했으며 미분류 파일은 없다.

| Classification | Count | 핵심 판단 |
|---|---:|---|
| `KEEP` | 85 | 현재 Runtime, 정본, 테스트, CI, Guard 또는 재현성 역할이 유효함 |
| `MOVE_CANDIDATE` | 5 | 역할은 필요하지만 목표 책임구조와 현재 위치가 다름 |
| `UPDATE_REQUIRED` | 7 | 경로는 유효하지만 현재 main 또는 확인된 근거와 상태·내용이 어긋남 |
| `ARCHIVE_CANDIDATE` | 5 | 현재 정본은 아니지만 결정·실험·감사 이력으로 보존 가치가 있음 |
| `DELETE_CANDIDATE` | 0 | 삭제의 11개 필수조건을 모두 충족한 자산이 없음 |

핵심 결론은 다음과 같다.

1. 현재 Python 수집·분석·추천 Application Service는 삭제하거나 즉시 재배치할 대상이
   아니다. 786개 테스트와 Project Guard가 안전계약을 보호한다.
2. `README.md`, `PROJECT_STATUS.md`, 분석·Dataset·제품 문서 7개에는 현재 main 또는
   확인된 증거와 맞지 않는 상태·근거 표현이 있어 먼저 정합화해야 한다.
3. 그다음 Vue·FastAPI 구현 전에 `apps/web`·`apps/api`의 책임, 데이터 공급방식과
   배포경계를 정하는 Architecture ADR이 필요하다.
4. 즉시 삭제 가능한 파일과 즉시 정리 가능한 코드는 0개다. 이동·보관·인터페이스
   정리는 PM 승인과 ADR 뒤의 별도 작업이어야 한다.
5. `RECOMMENDATION_OUTPUT_CONTRACT.md`의 v0.8.0 `PM 검토 대기`는 당시 버전 이력이다.
   후속 v0.9.0·v1.0.0이 PR #141로 main에 반영됐고 생산 Schema가 미구현이므로,
   문서 전체 `Draft`와 모순되지 않는다. 이 파일은 `KEEP`이다.

## 2. Audit 기준선과 main SHA

| 항목 | 확인 결과 |
|---|---|
| Repository | `shindonghyun0516-a11y/FreshManager` |
| local main | 기준 SHA 일치 |
| origin/main | 기준 SHA 일치 |
| GitHub main | 기준 SHA 일치 |
| PR #141 / Issue #140 | `MERGED` / `CLOSED · COMPLETED` |
| PR #143 / Issue #142 | `MERGED` / `CLOSED · COMPLETED` |
| main CI | 기준 SHA에서 `completed · success` |
| Audit Branch | `docs/issue-144-repository-readiness-audit` |
| Audit Issue | #144 `OPEN` |
| 시작 Worktree | Tracked 0, Staged 0, Untracked 0 |

기본 local main의 보호파일은 Audit 전후 SHA-256을 값 노출 없이 비교했다.

| 보호파일 | 시작 상태 | 전·후 SHA-256 비교 | Audit 중 추가변경·Stage |
|---|---|---|---|
| `.gitignore` | `M` | MATCH | 없음 |
| `.claude/hooks/block_main_branch_writes.py` | `??` | MATCH | 없음 |
| `.claude/settings.json` | `??` | MATCH | 없음 |
| `CLAUDE.md` | `??` | MATCH | 없음 |

Inventory 기준은 보고서 생성 전 기준 SHA의 `git ls-files` 결과다. 이 보고서 자체는
Audit 산출물이므로 102개 기준선 Inventory에 포함하지 않는다. 실제 Secret, 추적되지
않은 보호파일, 저장소 밖 Dataset·Run Output, 가상환경과 Cache는 조사대상에서 제외했다.

## 3. 총 Git 추적파일 수

**102개**. 부록의 경로 집합과 기준 SHA의 추적 경로 집합은 일치하며 누락·추가가 없다.

## 4. 파일유형별 개수

상호 배타적으로 분류했다. `tests/fixtures/`는 운영 Data가 아니라 Test 입력으로 센다.

| Type | Count |
|---|---:|
| Code | 24 |
| Test | 29 |
| Document | 35 |
| Data | 6 |
| Config | 6 |
| Workflow | 2 |
| **Total** | **102** |

## 5. Directory별 현재 역할

| Directory | 현재 역할 | 판정 |
|---|---|---|
| Repository Root | 진입문서, 상태 정본, 환경·Git·ML Dependency 계약 | 고정경로와 상태 정렬 필요 |
| `.github/` | Issue·PR 템플릿, Guard·전체시험·ML Runtime CI | 현행 유지 |
| `ai-context/` | PM 결정·ADR 이력과 장기 맥락 복원 | 현행 유지; 상태 정본 아님 |
| `data/reference/` | 공식 Area·패널 기준과 Pilot prototype 선택지가 혼재 | Pilot prototype만 이동 후보 |
| `data/samples/` | 네트워크 없는 공식 응답 샘플 | 현행 유지 |
| `docs/analysis/` | 분석 방법론과 역사 분석 결과 | 현행 정본과 history 분리 필요 |
| `docs/data/` | 데이터·백업·필드·Snapshot·Dataset 계약 | 일부 구현상태 갱신 필요 |
| `docs/engineering/` | Harness·개발절차·기술 정본 | Harness architecture만 이동 후보; TRD는 상태를 Status에 위임 |
| `docs/product/` | 제품·Area/Spot·Pilot·Recommendation 계약과 조사 | 정본 갱신 및 역사 조사 분리 필요 |
| `docs/rules/` | 코딩·수집·Git·ML·보안 불변규칙 | 현행 유지 |
| `docs/testing/` | Guard ID·보고·Engineering Gate 정본 | 현행 유지 |
| `docs/superpowers/plans/` | 과거 EG-8C 실행계획 | history 이동 후보 |
| `etc/` | 비개발자 수집 실행가이드 | `docs/data/` 이동 후보 |
| `freshmanager/` | 수집, 불변저장, 분석, ML, Area 추천 Application Service | 현행 유지; ADR 전 재배치 금지 |
| `interview/` | Gate C 인터뷰 계획과 합성 응답 | `docs/analysis/` 이동 후보 |
| `scripts/` | 고정 Project Guard 진입점 | 현행 유지 |
| `tests/` | 786개 Offline 계약시험과 Fixture | 현행 유지 |

## 6. 분류별 전체 개수

| Classification | Count | Confidence LOW |
|---|---:|---:|
| `KEEP` | 85 | 0 |
| `MOVE_CANDIDATE` | 5 | 0 |
| `UPDATE_REQUIRED` | 7 | 0 |
| `ARCHIVE_CANDIDATE` | 5 | 0 |
| `DELETE_CANDIDATE` | 0 | 0 |

사용한 분류값은 위 다섯 개뿐이다. 모든 판정은 현재 파일, Import·Test·CI·Guard·Link,
Git 이력과 현재 GitHub 상태에서 직접 확인했다.

## 7. KEEP 목록

KEEP 85개는 아래 명시적 파일군으로 설명한다. 각 경로의 최종 분류·Confidence·Risk는
부록에 다시 기록한다.

| Path 또는 명시적 파일군 | Type | Current Role | Runtime Role | References | Source of Truth | Classification | Confidence | Evidence | Risk | Proposed Target | Required Follow-up | PM Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `.env.example`, `.gitignore` | Config | Secret placeholder와 Git 보호경계 | None | Guard H-201·H-202·H-206, CI | Yes | KEEP | HIGH | 고정 보안계약이며 실제 Secret 없음 | CRITICAL | 현재 경로 | 보호상태 유지 | PENDING |
| `AGENTS.md` | Document | 세션 행동·승인·보안 진입정본 | None | Guard H-001, 전체 Workflow | Yes | KEEP | HIGH | 고정 진입점이며 현재 지시와 일치 | HIGH | 현재 경로 | 없음 | PENDING |
| `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md` | Config | GitHub 작업·검토 증거 템플릿 | None | Development·Git Workflow | Supporting | KEEP | HIGH | 활성 GitHub 입력경로 | MEDIUM | 현재 경로 | 없음 | PENDING |
| `.github/workflows/ci.yml`, `.github/workflows/ml-runtime.yml` | Workflow | Guard·전체시험과 ML Runtime 검증 | Internal / Experimental | Guard, tests, `requirements-ml.txt` | Yes / Supporting | KEEP | HIGH | PR·main Trigger와 최소 읽기권한 사용 | HIGH | 현재 경로 | Web/API CI는 기존 CI를 대체하지 말고 별도 ADR 후 추가 | PENDING |
| `requirements-ml.txt` | Config | 승인된 ML 직접 Dependency 고정 | Experimental | 두 CI와 EG-8C modeling | Yes | KEEP | HIGH | `scikit-learn==1.6.1` 한 줄 | HIGH | 현재 경로 | 없음 | PENDING |
| `ai-context/*` 3개 | Document | Decision·ADR·장기 맥락 이력 | None | Root 진입문서와 정본문서 | Yes / Supporting | KEEP | HIGH | 현재 상태는 `PROJECT_STATUS.md`에 위임 | HIGH | 현재 경로 | 없음 | PENDING |
| 현행 Data 문서 3개: Backup Plan, Field Dictionary, Manual Intake | Document | 백업·필드·반입 계약 | Product / Internal | 코드·Guard·분석문서 | Yes | KEEP | HIGH | 현재 생산·검증 계약을 소유 | HIGH | 현재 경로 | 없음 | PENDING |
| 현행 Product 문서 2개: EG6 Panel, Recommendation Contract | Document | 정적패널·출력계약 | Product | 코드·데이터·Decision·Guard | Yes | KEEP | HIGH | 정적 Master·Draft Schema 경계를 보존 | HIGH | 현재 경로 | 없음 | PENDING |
| Rules 5개 | Document | 코딩·수집·Git·ML Experiment·보안 규칙 | None / Experimental | AGENTS, CI, Guard, tests | Yes | KEEP | HIGH | 상호 책임이 분리된 현행 규칙 | HIGH | 현재 경로 | 없음 | PENDING |
| Testing 문서 3개 | Document | Guard ID·보고·Gate 정본 | None | Guard script, tests, AGENTS | Yes | KEEP | HIGH | 검사 ID와 Gate의 유일한 기준 | CRITICAL | 현재 경로 | 없음 | PENDING |
| `docs/engineering/DEVELOPMENT_WORKFLOW.md` | Document | Parent·병렬 Worktree 실무절차 | None | Git Workflow, templates | Yes | KEEP | HIGH | 단독 Workflow와 적용범위가 다름 | MEDIUM | 현재 경로 | 없음 | PENDING |
| `docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`, `docs/data/FIELD_DICTIONARY.md`, `docs/data/MANUAL_V3_SNAPSHOT_INTAKE.md`, `docs/engineering/FreshManager_TRD_v1.0.md`, `docs/product/EG6_AREA_SPOT_PANEL.md`, `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`, `docs/rules/*`, `docs/testing/*` | Document | 위 정본·지원문서의 명시적 경로 집합 | Product / Internal / Experimental / None | 각 코드·Guard·정본 링크 | Yes / Supporting | KEEP | HIGH | 부록의 15개 현행 Document와 동일 | HIGH | 현재 경로 | 위 파일군별 후속만 적용 | PENDING |
| `freshmanager/*` 23개 | Code | 수집·저장·분석·ML·Recommendation Core/Service | Product / Internal / Experimental | Import, CLI, 21 test modules, Guard | Yes | KEEP | HIGH | 모든 Module에 Runtime·검증·재현성 역할 존재 | HIGH | 현재 경로 | Architecture ADR 전 이동·삭제 금지 | PENDING |
| `scripts/project_guard_check.py` | Code | 47개 ID Offline Guard 구현 | Internal | CI, Guard Spec, 138개 Guard tests | Yes | KEEP | HIGH | 고정 실행 진입점 | CRITICAL | 현재 경로 | 없음 | PENDING |
| `tests/*` 29개 | Test | 정상·부정·보안·불변성·재현성 계약 | None | 24개 Code와 CI | Supporting | KEEP | HIGH | 786개 시험, 실제 외부호출 없음 | HIGH | 현재 경로 | 소유 계약 변경 때만 함께 변경 | PENDING |
| `data/reference/eg6_*`, `seoul_121_places.csv`, 공식 sample JSON | Data | 공식·내부 기준과 Offline 샘플 | Product / Internal | Collector, Guard, tests, docs | Yes | KEEP | HIGH | 참조·Sample 계약이 직접 소비됨 | CRITICAL | 현재 경로 | 불변 유지 | PENDING |

## 8. MOVE_CANDIDATE 목록

이 목록은 Issue #144 Audit 당시의 후보분류다. Issue #150 Draft에서는 문서 4건과
Inbound reference를 함께 이동·갱신했고, Data 파일인
`data/reference/pilot_spot_options.csv`만 미실행 후보로 남았다.

| Path | Type | Current Role | Runtime Role | References | Source of Truth | Classification | Confidence | Evidence | Risk | Proposed Target | Required Follow-up | PM Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `data/reference/pilot_spot_options.csv` | Data | 5개 Pilot Area·15개 PM 입력 Spot 선택지 | Experimental | Spot reader, Core, Service, Guard, 3 tests, Product docs | Yes | MOVE_CANDIDATE | HIGH | 공식 Area Master가 아니라 화면표시 prototype인데 `reference/`에 혼재 | HIGH | `data/prototype/pilot_spot_options.csv` | Loader 상수·Guard·Test·문서 링크를 함께 갱신 | PENDING |
| `docs/architecture/CODEX_HARNESS_ARCHITECTURE.md` | Document | Harness 구조·문서소유권 Architecture | None | AGENTS, README, Development Workflow, ML Rules | Yes | MOVE_CANDIDATE | HIGH | 목표 `docs/architecture/` 책임과 직접 일치 | HIGH | `docs/architecture/CODEX_HARNESS_ARCHITECTURE.md` | 고정 링크·Guard 영향 확인 후 별도 이동 | PENDING |
| `docs/data/DATA_COLLECTION_EXECUTION_GUIDE.md` | Document | 비개발자용 Apps Script·Python 수집 실행가이드 | Internal | Decision Log, ML Dataset Spec | Supporting | MOVE_CANDIDATE | HIGH | 현재 `etc/`보다 Data 실행계약과 함께 탐색하는 편이 명확함; 상단 Backup 표현도 본문과 정렬 필요 | MEDIUM | `docs/data/DATA_COLLECTION_EXECUTION_GUIDE.md` | 두 inbound 링크와 내부 상대링크 갱신, 상태문장 정렬 | PENDING |
| `docs/analysis/GATE_C_INTERVIEW_PLAN.md` | Document | Gate C 인터뷰 계획 | None | 직접 inbound 없음; Analysis Plan의 Gate C 책임과 연관 | Supporting | MOVE_CANDIDATE | HIGH | 독립 root 폴더보다 분석 방법론 하위가 역할에 맞음 | MEDIUM | `docs/analysis/GATE_C_INTERVIEW_PLAN.md` | PM 확인 수행 사실·privacy-safe Evidence Traceability·Gate C 판정을 분리해 연결 | PENDING |
| `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md` | Document | 공개자료 기반 합성 응답·코딩체계 | None | Analysis Plan Gate C | Supporting | MOVE_CANDIDATE | HIGH | 실제 인터뷰·직접 인용·Gate C 통과 근거가 아닌 합성자료 | HIGH | `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md` | 네 경계를 보존해 Analysis Plan 링크와 함께 정렬 | PENDING |

## 9. UPDATE_REQUIRED 목록

| Path | Type | Current Role | Runtime Role | References | Source of Truth | Classification | Confidence | Evidence | Risk | Proposed Target | Required Follow-up | PM Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `README.md` | Document | 첫 사용자·새 세션 안내 | None | AGENTS, Status, PRD/TRD, Guard 입력 | Supporting | UPDATE_REQUIRED | HIGH | Issue #70 Controller를 “구현 중”으로 설명하지만 PR #71로 main 반영·Issue 종료됨; 이후 EG-8·Pilot 상태도 축약되지 않음 | HIGH | 현재 경로 | 변동상태는 Status 링크로 위임하고 현행 단계 요약만 갱신 | PENDING |
| `PROJECT_STATUS.md` | Document | 현재 상태의 단일 운영 정본 | None | 모든 진입문서·Workflow | Yes | UPDATE_REQUIRED | HIGH | Manual V3 Intake를 `LOCAL_IMPLEMENTATION_COMPLETE_PENDING_PM_DIFF_REVIEW`, Commit·PR 없음으로 기록하지만 PR #114가 병합되고 Issue #113이 종료됨 | CRITICAL | 현재 경로 | 해당 상태와 후속 실제 Snapshot 이력을 현재 main 근거로 정렬 | PENDING |
| `docs/analysis/ANALYSIS_PLAN.md` | Document | EG-8 분석·평가 방법론 | Internal | Dataset Spec, Output Contract, Gates | Yes | UPDATE_REQUIRED | HIGH | EG-8D를 local PM review 대기로 남기지만 PR #110·#112가 main에 반영됨; 합성 matrix를 “인터뷰 결과”로 표현함 | HIGH | 현재 경로 | main 상태 갱신, 합성자료와 실제 인터뷰를 명확히 분리 | PENDING |
| `docs/data/ML_READY_DATASET_SPEC.md` | Document | EG-8A/8B Dataset 계약 | Experimental | EG-8A/C code, tests, Analysis, TRD | Yes | UPDATE_REQUIRED | HIGH | §2가 Python Loader와 Dataset을 모두 `NOT_IMPLEMENTED`로 기록하지만 구현·공식 Dataset·Manifest가 존재함 | HIGH | 현재 경로 | 계약은 유지하고 구현·공식 Run 상태를 Status 정본과 연결 | PENDING |
| `docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md` | Document | D-022 Area-first Web Pilot 계약 | Product | PRD, Decision Log, Output Contract | Yes | UPDATE_REQUIRED | HIGH | PM 확인 실제 인터뷰와 Git 정본 사이에 privacy-safe Evidence Traceability가 없음 | HIGH | 현재 경로 | 실제 인터뷰 수행 표현은 유지하고 개인정보 없는 요약·최소 Metadata·답변/해석·합성자료·Gate C 경계 중 승인된 최소 범위만 보완 | PENDING |
| `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md` | Document | Area·Spot 장기정책과 초기 Pilot 정책 | Product | Output Contract, Pilot data, D-020~D-022 | Supporting | UPDATE_REQUIRED | HIGH | D-021의 시스템 Area 추천을 초기 기본 흐름으로 설명하지만 D-022가 사용자 담당 Area 직접 선택으로 대체함 | HIGH | 현재 경로 | D-022 기본 흐름과 D-021 내부 분석 이력을 분리 | PENDING |
| `docs/product/FreshManager_PRD_v1.0.md` | Document | 공식 제품 요구사항 | Product | TRD, Status, Gates, Product contracts | Yes | UPDATE_REQUIRED | HIGH | PM 확인 실제 인터뷰와 Git 정본 사이에 privacy-safe Evidence Traceability가 없음 | HIGH | 현재 경로 | 실제 인터뷰 수행 표현은 유지하고 개인정보 없는 요약·최소 Metadata·답변/해석·합성자료·Gate C 경계 중 승인된 최소 범위만 보완; v1.6 `PM 검토 대기`는 별도 PM 판단 전 유지 | PENDING |

## 10. ARCHIVE_CANDIDATE 목록

이 목록은 Issue #144 Audit 당시의 후보분류다. Issue #150 Draft에서 5건을 삭제하지
않고 `docs/history/`로 이동했으며, 역사 배너와 inbound link를 보존했다.

| Path | Type | Current Role | Runtime Role | References | Source of Truth | Classification | Confidence | Evidence | Risk | Proposed Target | Required Follow-up | PM Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `docs/history/requirements/requirements-definition-freshmanager-poc-v0.4.md` | Document | PRD 이전 요구사항 기준선 | None | AGENTS, Analysis, Field Dictionary, Harness, PRD, Data Rules | No | ARCHIVE_CANDIDATE | HIGH | 문서 첫머리가 역사 문서·현행 기준 아님을 명시; 현재 정본은 PRD/TRD | LOW | `docs/history/requirements/requirements-definition-freshmanager-poc-v0.4.md` | 6개 inbound 링크 갱신과 역사 배너 보존 | PENDING |
| `docs/history/analysis/EG5_DATA_ANALYSIS_REPORT.md` | Document | 대표 3 Area 실제수집 역사 분석증거 | Internal | PRD, EG6 Panel | Supporting | ARCHIVE_CANDIDATE | HIGH | 현재 실행방법이 아니라 EG-5 단면 증거; 현행 분석 정본은 Analysis Plan | LOW | `docs/history/analysis/EG5_DATA_ANALYSIS_REPORT.md` | 2개 inbound 링크 갱신, 결과 원문 보존 | PENDING |
| `docs/history/research/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md` | Document | Issue #126 당시 원격 Spot 준비도 평가 | Internal | Decision Log, current Policy | No | ARCHIVE_CANDIDATE | HIGH | D-020·후속 계약에 반영된 과거 조사이며 자체 대체상태를 명시 | LOW | `docs/history/research/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md` | 2개 inbound 링크와 외부 근거 유지 | PENDING |
| `docs/history/research/PILOT_AREA_SELECTION_ASSESSMENT.md` | Document | D-021 5개 Area 선정 조사 | Internal | 직접 inbound 없음; 후속 D-021/D-022 결정 | No | ARCHIVE_CANDIDATE | HIGH | D-022가 웹 기본 흐름을 사용자 Area 선택으로 바꿨으나 선정 이력은 재현가치가 있음 | LOW | `docs/history/research/PILOT_AREA_SELECTION_ASSESSMENT.md` | D-021 역사 배너와 outbound 링크 검증 | PENDING |
| `docs/history/plans/2026-07-27-eg8c-ml-modeling.md` | Document | 과거 EG-8C Modeling 실행계획 | Experimental | 코드에 직접 inbound 없음; Analysis·Status가 결과 정본 | No | ARCHIVE_CANDIDATE | HIGH | 첫머리가 Ridge 자동탐색 계획이 후속 결정으로 대체됐음을 명시 | MEDIUM | `docs/history/plans/2026-07-27-eg8c-ml-modeling.md` | 실행지시로 오독되지 않게 역사 배너·결과 링크 유지 | PENDING |

## 11. DELETE_CANDIDATE 목록

**0개다.** 생산 Import·CLI·Script·Test·CI·Guard·정본 Link·Data/Manifest 관계와
감사·실험·재현성 가치를 모두 확인했다. 완전한 대체자산과 기능손실 0을 동시에
입증한 파일이 없어 삭제 후보를 만들지 않았다.

## 12. 코드 책임 Matrix

모든 Code는 `KEEP`, Confidence `HIGH`, PM Decision `PENDING`이다. 비공개 함수의
모듈 간 사용은 현재 시험된 내부 구현이므로 그 사실만으로 `UPDATE_REQUIRED`로
올리지 않는다. FastAPI 경계를 정한 ADR 뒤에만 지원 인터페이스를 검토한다.

| Path | 역할 분류 | Current Role / Runtime Role | 주요 References | CLI | Risk |
|---|---|---|---|---|---|
| `freshmanager/__init__.py` | UTILITY | 최소 package public surface / Internal | collector·config·storage export | No | MEDIUM |
| `freshmanager/batch_id.py` | OUTPUT_SAFETY | canonical Batch ID 검증 / Product | storage·EG6/7·backup·intake tests | No | HIGH |
| `freshmanager/config.py` | DATA_INTAKE | env 읽기·Secret masking / Product | live collectors, Guard | No | HIGH |
| `freshmanager/storage.py` | OUTPUT_SAFETY | 비덮어쓰기 저장·배타 예약 / Product | collector·EG5/6, Guard | No | CRITICAL |
| `freshmanager/collector.py` | PRODUCT_CORE | 장소조회·응답 parsing·1곳 수집 / Product | live·EG5/6/7·offline | No | HIGH |
| `freshmanager/http_adapter.py` | DATA_INTAKE | 제한된 서울시 HTTP transport / Product | live collectors, security tests | No | HIGH |
| `freshmanager/offline.py` | INTERNAL_ANALYSIS | 공식 sample 전용 EG-4 경로 / Internal | Guard H-506, tests | Yes | HIGH |
| `freshmanager/live.py` | DATA_INTAKE | 승인 gated POI072 live CLI / Product | collector·adapter·tests | Yes | CRITICAL |
| `freshmanager/eg5.py` | DATA_INTAKE | 고정 3 Area 수집 / Product | collector·storage·tests | Yes | HIGH |
| `freshmanager/eg6b.py` | OUTPUT_SAFETY | 13 Area 단일 Batch 조립·Manifest / Product | EG7·backup·Guard·tests | Yes | CRITICAL |
| `freshmanager/backup.py` | OUTPUT_SAFETY | 검증된 로컬 Sync 복사·Receipt / Product | EG6B·Guard·53 tests | Yes | CRITICAL |
| `freshmanager/eg7.py` | INTERNAL_ANALYSIS | 5분 Pilot Controller·파생 index / Internal | EG6B·backup·41 tests | Yes | HIGH |
| `freshmanager/eg8a.py` | INTERNAL_ANALYSIS | v3 Loader·정규화·품질·Manifest / Internal | EG8B/C/D·intake·65 tests | No | HIGH |
| `freshmanager/eg8b.py` | INTERNAL_ANALYSIS | Dataset profile·Forecast join / Internal | B2a/B2b/C·29 tests | No | MEDIUM |
| `freshmanager/eg8b_b2a.py` | INTERNAL_ANALYSIS | 단일일자 잠정 backtest / Experimental | EG8B·20 tests | No | MEDIUM |
| `freshmanager/eg8b_b2b.py` | INTERNAL_ANALYSIS | 단기 다일자 잠정 backtest / Experimental | EG8B·29 tests | No | MEDIUM |
| `freshmanager/eg8c_features.py` | EXPERIMENTAL_ML | leakage-safe Dataset 공개 / Experimental | modeling·EG8D·intake·95 tests | Yes | CRITICAL |
| `freshmanager/eg8c_modeling.py` | EXPERIMENTAL_ML | 잠긴 Dataset 모델 비교 / Experimental | ML CI·31 tests | No | HIGH |
| `freshmanager/eg8d_area_priority.py` | INTERNAL_ANALYSIS | Area 변화순서·최신성 Gate / Internal | Pilot Core·70 tests | Yes | HIGH |
| `freshmanager/manual_snapshot_intake.py` | DATA_INTAKE | 불변 Manual v3 Snapshot 반입 / Internal | EG8A/C·32 tests | No | CRITICAL |
| `freshmanager/pilot_spot_options.py` | APPLICATION_SERVICE | 정적 5 Area Spot Master reader / Product | Core·Service·Guard·6 tests | No | HIGH |
| `freshmanager/pilot_area_recommendation.py` | APPLICATION_SERVICE | 메모리 내 5 Area 비교 Core / Internal | EG8D·Spot reader·13 tests | No | HIGH |
| `freshmanager/pilot_recommendation_service.py` | APPLICATION_SERVICE | JSON-safe Pilot ViewModel / Product | Core·19 tests | No | HIGH |
| `scripts/project_guard_check.py` | OUTPUT_SAFETY | 47-ID Offline Guard / Internal | CI·Guard Spec·138 tests | Yes | CRITICAL |

## 13. 문서 정본 Matrix

| Path | Current Role | Source of Truth | Classification | 현재 또는 대체 정본 | 핵심 근거 |
|---|---|---|---|---|---|
| `AGENTS.md` | 행동·승인·보안 | Yes | KEEP | 자체 | 고정 세션 진입점 |
| `PROJECT_STATUS.md` | 현재 운영상태 | Yes | UPDATE_REQUIRED | 자체 | Manual Intake 상태 drift |
| `README.md` | 소개·탐색 | Supporting | UPDATE_REQUIRED | Status·PRD·TRD | EG-7 과거상태 잔존 |
| `docs/history/requirements/requirements-definition-freshmanager-poc-v0.4.md` | 과거 요구사항 | No | ARCHIVE_CANDIDATE | PRD·TRD | 자체 역사 배너 |
| `ai-context/ARCHITECTURE_DECISIONS.md` | ADR 이력 | Yes | KEEP | 자체 | 대안·영향 보존 |
| `ai-context/DECISION_LOG.md` | PM 결정 이력 | Yes | KEEP | 자체 | D-020~D-022 근거 |
| `ai-context/PROJECT_MEMORY.md` | 장기 맥락복원 | Supporting | KEEP | Status·PRD·TRD | 현재상태 비복제 |
| `docs/analysis/ANALYSIS_PLAN.md` | 분석 방법론 | Yes | UPDATE_REQUIRED | 자체 | EG-8D·Gate C 표현 drift |
| `docs/history/analysis/EG5_DATA_ANALYSIS_REPORT.md` | EG-5 역사증거 | Supporting | ARCHIVE_CANDIDATE | Analysis Plan·Status | 실행 정본 아님 |
| `docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md` | Backup·CSV 계약 | Yes | KEEP | 자체 | 코드·Guard 연결 |
| `docs/data/FIELD_DICTIONARY.md` | 필드 의미 | Yes | KEEP | 자체 | H-707·데이터 계약 |
| `docs/data/MANUAL_V3_SNAPSHOT_INTAKE.md` | Manual Intake 계약 | Yes | KEEP | 자체 | 생산 parser와 연결 |
| `docs/data/ML_READY_DATASET_SPEC.md` | Dataset 계약 | Yes | UPDATE_REQUIRED | 자체·Status | 구현상태 drift |
| `docs/architecture/CODEX_HARNESS_ARCHITECTURE.md` | Harness 구조 | Yes | MOVE_CANDIDATE | 자체 | architecture 책임 |
| `docs/engineering/DEVELOPMENT_WORKFLOW.md` | 병렬 개발절차 | Yes | KEEP | 자체 | Git Workflow와 범위분리 |
| `docs/engineering/FreshManager_TRD_v1.0.md` | 기술 요구 | Yes | KEEP | 자체·Status | 구성표는 완료상태표가 아니며 Status에 위임 |
| `docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md` | D-022 Web Pilot 계약 | Yes | UPDATE_REQUIRED | 자체·D-022 | PM 확인 실제 인터뷰와 Git 정본 사이 privacy-safe Evidence Traceability 부재 |
| `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md` | Area·Spot 정책 | Supporting | UPDATE_REQUIRED | D-022·Area-first Contract | 초기 흐름 불일치 |
| `docs/history/research/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md` | 원격근거 역사평가 | No | ARCHIVE_CANDIDATE | D-020·Policy | 대체 이력 |
| `docs/product/EG6_AREA_SPOT_PANEL.md` | 정적 13 Area Panel | Yes | KEEP | 자체 | Guard H-703 입력 |
| `docs/product/FreshManager_PRD_v1.0.md` | 제품 요구 | Yes | UPDATE_REQUIRED | 자체 | PM 확인 실제 인터뷰와 Git 정본 사이 privacy-safe Evidence Traceability 부재 |
| `docs/history/research/PILOT_AREA_SELECTION_ASSESSMENT.md` | D-021 선정조사 | No | ARCHIVE_CANDIDATE | D-021·D-022 | 현재 기본흐름 아님 |
| `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` | 출력계약 | Yes | KEEP | 자체 | v1.0.0, 생산 Schema 미구현 |
| `docs/rules/CODING_RULES.md` | 코드 규칙 | Yes | KEEP | 자체 | Guard 입력 |
| `docs/rules/DATA_COLLECTION_RULES.md` | 수집 규칙 | Yes | KEEP | 자체 | 5분·원본 계약 |
| `docs/rules/GIT_WORKFLOW.md` | 단독 Git 절차 | Yes | KEEP | 자체 | Development Workflow와 범위분리 |
| `docs/rules/ML_EXPERIMENT_RULES.md` | ML Experiment 규칙 | Yes | KEEP | 자체 | Modeling Plan과 책임분리 |
| `docs/rules/SECURITY_RULES.md` | 보안 규칙 | Yes | KEEP | 자체 | Secret·Git 계약 |
| `docs/history/plans/2026-07-27-eg8c-ml-modeling.md` | 과거 Modeling Plan | No | ARCHIVE_CANDIDATE | Analysis Plan·D-017 | 후속 결정으로 대체 |
| `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md` | Guard 보고형식 | Yes | KEEP | 자체 | 필수 보고계약 |
| `docs/testing/PROJECT_GUARD_SPEC.md` | Guard ID·판정 | Yes | KEEP | 자체 | 유일한 검사정본 |
| `docs/testing/QUALITY_GATES.md` | EG 진입·통과 | Yes | KEEP | 자체 | 상태는 Status에 위임 |
| `docs/data/DATA_COLLECTION_EXECUTION_GUIDE.md` | 수집 실행가이드 | Supporting | MOVE_CANDIDATE | Data Rules·Status | 위치와 일부 상태정렬 필요 |
| `docs/analysis/GATE_C_INTERVIEW_PLAN.md` | Gate C 인터뷰 계획 | Supporting | MOVE_CANDIDATE | Analysis Plan | 분석경로로 이동 적합 |
| `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md` | 공개자료 기반 합성 응답 | Supporting | MOVE_CANDIDATE | 실제 인터뷰·직접 인용·Gate C 증거 아님 | 합성자료 표시 보존 |

## 14. Data·Manifest Matrix

| Path 또는 자산 | Current Role | Runtime Role | References | Source of Truth | Classification | Confidence | Evidence / Risk | Proposed Target / Follow-up | PM Decision |
|---|---|---|---|---|---|---|---|---|---|
| `data/reference/seoul_121_places.csv` | 공식 121 Area 유일 기준 | Product | Collector·Guard·tests | Yes | KEEP | HIGH | CRITICAL; H-101~112 | 현재 경로·불변 유지 | PENDING |
| `data/reference/eg6_area_panel.csv` | 승인 13 Area panel | Internal | EG6B·backup·Guard | Yes | KEEP | HIGH | HIGH; Manifest reference hash | 현재 경로 유지 | PENDING |
| `data/reference/eg6_spot_master.csv` | 13 Candidate Anchor | Internal | EG6B·Spot tests·Guard | Yes | KEEP | HIGH | HIGH; 확정 판매지점 아님 | 현재 경로 유지 | PENDING |
| `data/reference/eg6_sdot_links.csv` | S-DoT 공간 보조연결 | Internal | EG6B·Guard·tests | Yes | KEEP | HIGH | HIGH; Area 대체 아님 | 현재 경로 유지 | PENDING |
| `data/reference/pilot_spot_options.csv` | 15 prototype Spot 선택지 | Experimental | Pilot code·Guard·tests | Yes | MOVE_CANDIDATE | HIGH | HIGH; 공식 Reference와 책임혼재 | `data/prototype/` 이동은 별도 승인 | PENDING |
| `data/samples/population_yeouido_sample.json` | 공식 Offline 실응답 sample | Internal | Offline CLI·Guard·tests | Yes | KEEP | HIGH | HIGH; Fixture로 이동 금지 | 현재 경로 유지 | PENDING |
| `tests/fixtures/` 8개 | 정상·오류경계 재현 입력 | None | EG-8A·Project Guard tests | Supporting | KEEP | HIGH | MEDIUM; 운영 Data가 아닌 Test 자산 | 소유 Test와 함께 유지 | PENDING |
| EG-6B `manifest.json` | 외부 Batch 증거 | Product | EG6B·backup | Yes | KEEP | HIGH | 저장소 밖 불변 output | Git 추적 금지 | PENDING |
| Manual `snapshot_manifest.json` | 외부 Snapshot lineage | Internal | Manual intake·EG8A adapter | Yes | KEEP | HIGH | 저장소 밖 Final, no-overwrite | Git 추적 금지 | PENDING |
| EG-8C `dataset_manifest.json` | 공식 Dataset lock | Experimental | EG8C·modeling·EG8D | Yes | KEEP | HIGH | 기존·신규 공식 Manifest hash 불변 | Git 추적 금지 | PENDING |
| EG-8D `area_priority_manifest.json` | Area 분석 결과 증거 | Internal | EG8D result verification | Yes | KEEP | HIGH | 기존 결과 hash 불변 | Git 추적 금지 | PENDING |

Git에 추적된 운영 Manifest는 0개다. 이는 누락이 아니라 원본·참조자산과 외부 불변
실행산출물을 분리한 계약이다.

읽기 전용 지문 재확인 결과는 다음과 같다. 저장소 밖 실제 경로는 보안·이식성 원칙에
따라 기록하지 않는다.

| 검증 대상 | SHA-256 | 결과 |
|---|---|---|
| 잠긴 공식 EG-8C Dataset Manifest | `388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771` | MATCH |
| 신규 공식 EG-8C Dataset Manifest | `2980db976dcfedb7631706cba0ad333295a7df2379f5a35a7281c0efc8f5116f` | MATCH |
| EG-8D Area Priority Manifest | `ddcf29b9387016c109ae23b0237f842ad235946f8ed98d387fd11746869984bb` | MATCH |

## 15. CI·Guard·Test 의존관계

```text
pull_request / main push
  → .github/workflows/ci.yml
    → scripts/project_guard_check.py
    → requirements-ml.txt 설치
    → tests/test_*.py 전체 발견·실행

ML 관련 경로 변경
  → .github/workflows/ml-runtime.yml
    → Python 3.12
    → scikit-learn 1.6.1 검증
```

- Project Guard: 47개 ID 중 현재 집계 `PASS=43, FAIL=0, WARN=0, SKIP=4`.
- Tests: 21개 Python test module과 8개 fixture, 총 786개 시험.
- 모든 Test는 생산코드의 정상·부정·중단·불변성·Secret 비노출 계약을 보호한다.
- `tests/test_project_guard_check.py`는 Guard registry와 변경안전성을 직접 검증한다.
- Vue·FastAPI CI는 아직 없다. 도구 설치나 Workflow 추가는 Architecture ADR과 구현
  Issue 뒤에 기존 CI를 약화하지 않는 방식으로 설계해야 한다.

필수 필드는 부록의 개별 Path와 아래 명시적 Test 파일군을 결합해 적용한다. 모든
Test 파일군은 Type `Test`, Runtime Role `None`, Source of Truth `Supporting`,
Classification `KEEP`, Confidence `HIGH`, Proposed Target `현재 경로`, PM Decision
`PENDING`이다.

| 명시적 Path 파일군 | Current Role | References | Evidence | Risk | Required Follow-up |
|---|---|---|---|---|---|
| `test_backup.py`, `test_batch_id.py`, `test_eg4_collector.py`, `test_eg5.py`, `test_eg6b.py`, `test_http_adapter.py`, `test_live.py` | 수집·저장·Live·Secret·Backup 안전계약 | Collector·Storage·EG5/6·Backup·HTTP | 정상·실패·중단·비노출 경계 | HIGH | 소유 생산계약 변경 때만 함께 변경 |
| `test_eg6_reference_data.py`, `test_eg7.py` | 정적 Panel·5분 Pilot 계약 | Reference data·EG7·Guard | 패널·계획·lock·파생 index | HIGH | 운영 lifecycle 변경 때만 함께 변경 |
| `test_eg8a.py`, `test_eg8b.py`, `test_eg8b_b2a.py`, `test_eg8b_b2b.py`, `test_eg8c_features.py`, `test_eg8c_modeling.py`, `test_eg8d_area_priority.py`, `test_manual_snapshot_intake.py` | Dataset·ML·Area 분석·불변공개 계약 | EG8A~D·Manual intake | Schema·leakage·publication·freshness·lineage | HIGH | Data/Artifact 계약 변경 때만 함께 변경 |
| `test_pilot_area_recommendation.py`, `test_pilot_recommendation_service.py`, `test_pilot_spot_options.py` | Pilot Core·ViewModel·Spot 선택계약 | 세 Pilot Module·prototype CSV | 사용자 선택·비추천·JSON-safe 경계 | HIGH | API ADR 뒤 interface가 바뀔 때만 변경 |
| `test_project_guard_check.py` | 47-ID Guard registry·격리·변경안전 | Guard script·Spec·fixtures | 138개 Guard 자체 계약 | CRITICAL | Guard ID 정본 변경 때만 변경 |
| `tests/fixtures/` 8개 | 정상·오류경계 재현입력 | EG8A·Guard tests | 운영 Data가 아닌 결정적 Test 입력 | MEDIUM | 소유 Test와 함께 보존 |

## 16. Root·목표구조 Gap

아래 구조는 모두 현재 부재하며 이번 Audit에서는 생성하지 않는다.

| Target | 역할 | 포함할 자산 | 포함하면 안 되는 자산 | 기존 경로와 관계 | 생성 시점 |
|---|---|---|---|---|---|
| `apps/web` | Area-first Vue UI | 화면·Component·UI test·build config | API Secret, Raw/Manifest, Python 분석코드 | Area-first Contract를 소비 | Web Stack·배포 ADR와 구현 Issue 승인 뒤 |
| `apps/api` | 최소 FastAPI HTTP 경계 | 승인된 adapter·schema·API tests | Collector, 운영 DB, 추천 자동실행, Secret | 기존 Pilot Service 재사용범위를 ADR로 결정 | API·데이터공급 ADR 뒤 |
| `data/prototype` | 비운영 화면 prototype data | 승인된 Pilot Spot options | 공식 Area Master, Raw, Forecast, Manifest | 현재 Pilot CSV의 역할과 일치 | 이동 전용 Issue 승인 뒤 |
| `docs/architecture` | 모듈·데이터흐름·ADR·Audit | 이 Audit, Web/API/data ADR | 일일 상태, 원본, 실행로그 | Engineering TRD를 대체하지 않음 | Audit 보고서부터; 추가문서는 ADR 승인 뒤 |
| `docs/history` | 대체된 계획·조사·분석 이력 | 5개 Archive 후보 | 현행 PRD/TRD/Rules/Gates | 인바운드 링크 보존 필요 | 파일별 Archive 승인 뒤 |
| `docs/README.md` | docs 탐색색인 | 정본·지원·history 링크 | 상태 복제, 새 정책 | Root README를 대체하지 않음 | 첫 구조이동 Issue와 함께 |

현재 Repository는 Python PoC와 Application Service의 검증기반은 갖췄지만, Web/API
구성·데이터 공급·배포·보안경계가 승인되지 않아 바로 구현을 시작할 상태는 아니다.

## 17. 위험도 우선순위

| Priority | Severity | 위험 | 영향 | 최소 대응 |
|---:|---|---|---|---|
| 1 | MAJOR | 7개 정본·지원문서 상태·근거 drift | Architecture가 낡은 상태나 추적되지 않은 Evidence 전제를 사용할 수 있음 | 문서 정합화 Issue |
| 2 | MAJOR | Web/API Architecture와 데이터 공급계약 부재 | 구현이 기존 Collector·외부 Result Root·내부 Service 경계를 임의로 침범할 수 있음 | 문서 정합화 뒤 Architecture ADR |
| 3 | MINOR | 5개 자산의 책임경로 혼재 | 탐색성과 변경영향 파악 저하 | ADR 뒤 원자적 이동 |
| 4 | MINOR | 5개 역사자산이 현행 탐색경로에 혼재 | 과거 지시를 현재 지시로 오독할 수 있음 | history 이동·배너 보존 |
| 5 | NOTE | 내부 Module 사이 비공개 helper 호출 | 현재 시험은 통과하지만 HTTP adapter 경계로 노출하기 부적절 | API ADR 뒤 최소 내부 interface 검토 |

### Findings 집계

- BLOCKER: 0
- MAJOR: 2
- MINOR: 2
- NOTE: 1

실제 프래시매니저 인터뷰 수행은 `PM_CONFIRMED`이고, Git Evidence는 `NOT_TRACKED`다.
합성 matrix는 실제 인터뷰 또는 Gate C 통과 증거가 아니며 Gate C는 별도로 평가해야
한다. Decision Log의 D-022는 PM 결정 이력 자체이므로 `KEEP`하되 이 Evidence
Traceability 제한을 함께 읽어야 한다.

## Code Cleanup Readiness

### Audit 직후 PM 승인 시 정리 가능한 코드

**0개.** 현재 코드를 삭제·이동하거나 이름만 정리할 근거가 없다.

### 최소 진입조건 충족 후에만 정리 가능한 코드

아래 **7개 Interface Seam 후보 범위**는 모두 현재 `KEEP`이다. 코드 정리는 다음
조건을 모두 충족한 뒤에만 재평가한다.

1. Audit PR #145 병합
2. 문서 7건 정합화
3. Web/API·데이터 공급 Architecture ADR 승인·병합
4. ADR 기준으로 Interface Seam 변경 필요성 재평가

| 순위 | 코드 | 분류 | 정리방식 | 위험 | 선행조건 |
|---:|---|---|---|---|---|
| 1 | `eg8d_area_priority.py` + `pilot_area_recommendation.py` | KEEP | read-only Area priority 내부 interface 검토 | HIGH | `apps/api` 입력계약 ADR |
| 2 | `eg8c_features.py` + modeling·EG8D·manual callers | KEEP | 배타 공개 primitive 소유자 명시 | CRITICAL | publication safety ADR·실패경로 tests |
| 3 | `eg6b.py` + `eg7.py` | KEEP | preflight·reservation 내부 interface 검토 | CRITICAL | 운영 lifecycle ADR·동시성 tests |
| 4 | `pilot_spot_options.py` | KEEP | prototype data 경로만 승인 시 갱신 | HIGH | Data 이동 승인·Guard 동시갱신 |
| 5 | `pilot_recommendation_service.py` | KEEP | HTTP adapter가 감쌀 최소 surface 결정 | HIGH | FastAPI schema ADR |
| 6 | `eg8b.py`·`eg8b_b2a.py`·`eg8b_b2b.py` | KEEP | 중복 output 검증은 공통계약이 생길 때만 검토 | HIGH | Artifact root ADR |
| 7 | `live.py` + `eg5.py` | KEEP | 유사 transport 조립을 형태만 보고 합치지 않음 | HIGH | Live approval contract 동등성 증명 |

### 삭제하면 안 되는 보호코드

`backup.py`, `batch_id.py`, `config.py`, `storage.py`, `collector.py`,
`http_adapter.py`, `offline.py`, `live.py`, `eg6b.py`, `eg7.py`,
`eg8c_features.py`, `manual_snapshot_intake.py`, Project Guard와 그 계약시험은
데이터손실·Secret·Live 실행·불변공개 경계다.

### 추가 증거가 필요한 코드

위 7개 ADR 이후 검토파일의 실제 변경 필요성은 `apps/api`가 소비할 입력, 외부 Result
Root 읽기 방식, 실행권한과 오류계약이 정해진 뒤에만 평가할 수 있다. 이번 Audit은
Runtime integration을 실행하지 않았으므로 해당 부분은 `NOT_EVALUATED`다.

## 18. 권장 후속 Issue

아래 표는 Issue #144 Audit 당시의 권고 이력이다. Priority 1은 Issue #146,
Priority 2는 Issue #148에서 완료됐고, 문서 MOVE·ARCHIVE는 Issue #150 Draft에
통합 반영됐다. `pilot_spot_options.csv` 이동은 여전히 미승인 후보이며 이번
작업에서 수행하지 않았다.

| Priority | 권장 제목 | 범위 | 산출물 |
|---:|---|---|---|
| 1 | `[Docs] Repository 상태·근거 불일치 7건 정합화` | UPDATE_REQUIRED 7개만 현행 main·확인된 증거와 정렬 | 기존 계약 확대 없는 문서 수정 |
| 2 | `[Architecture] Area-first Web/API 경계와 데이터 공급 계약` | Vue·FastAPI 구성, 기존 Service adapter, 외부 Result read-only 공급, Secret·배포·오류경계 | ADR 1개와 후속 구현파일 범위 |
| 3 | `[Structure] prototype·architecture·analysis 책임경로 이동` | MOVE_CANDIDATE 5개와 inbound reference | 이동·링크·Guard 검증 |
| 4 | `[History] 대체된 계획·조사·분석 문서 보관` | ARCHIVE_CANDIDATE 5개 | `docs/history/`와 docs index |

첫 후속은 Priority 1만 권장한다. 현재 정본 상태와 Evidence Traceability를 먼저
정리해야 Architecture ADR이 현행 근거를 사용할 수 있다. 새 제품요구나 기술결정은
이 문서 정합화 범위에 포함하지 않는다.

## 19. PM 결정목록

1. 이 Audit의 85/5/7/5/0 후보분류는 Issue #144 기준 승인 이력으로 보존한다.
2. 상태·근거 drift 7건 정합화는 Issue #146에서 완료됐다.
3. Web/API·데이터 공급 Architecture ADR은 Issue #148에서 완료됐다.
4. 문서 MOVE 4건과 ARCHIVE 5건은 Issue #150 Draft에 반영됐으며 PM 검토 대기다.
5. `pilot_spot_options.csv` 이동과 `DELETE_CANDIDATE=0`은 기존 상태를 유지한다.

## 20. 전체 파일 Inventory 부록

아래 102개가 기준 SHA의 `git ls-files` 전체 결과다. 각 행은 위 파일군·Matrix의
Current Role, Runtime Role, References, Source of Truth, Evidence, Proposed Target와
Required Follow-up을 상속한다. 별도 표시가 없는 KEEP의 Proposed Target은 현재 경로,
Required Follow-up은 없음이다.

| Path | Type | Classification | Confidence | Risk | PM Decision |
|---|---|---|---|---|---|
| `.env.example` | Config | KEEP | HIGH | HIGH | PENDING |
| `.github/ISSUE_TEMPLATE/parent_task.md` | Config | KEEP | HIGH | MEDIUM | PENDING |
| `.github/ISSUE_TEMPLATE/task.md` | Config | KEEP | HIGH | MEDIUM | PENDING |
| `.github/pull_request_template.md` | Config | KEEP | HIGH | MEDIUM | PENDING |
| `.github/workflows/ci.yml` | Workflow | KEEP | HIGH | HIGH | PENDING |
| `.github/workflows/ml-runtime.yml` | Workflow | KEEP | HIGH | MEDIUM | PENDING |
| `.gitignore` | Config | KEEP | HIGH | CRITICAL | PENDING |
| `AGENTS.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `PROJECT_STATUS.md` | Document | UPDATE_REQUIRED | HIGH | CRITICAL | PENDING |
| `README.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `ai-context/ARCHITECTURE_DECISIONS.md` | Document | KEEP | HIGH | MEDIUM | PENDING |
| `ai-context/DECISION_LOG.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `ai-context/PROJECT_MEMORY.md` | Document | KEEP | HIGH | MEDIUM | PENDING |
| `data/reference/eg6_area_panel.csv` | Data | KEEP | HIGH | HIGH | PENDING |
| `data/reference/eg6_sdot_links.csv` | Data | KEEP | HIGH | HIGH | PENDING |
| `data/reference/eg6_spot_master.csv` | Data | KEEP | HIGH | HIGH | PENDING |
| `data/reference/pilot_spot_options.csv` | Data | MOVE_CANDIDATE | HIGH | HIGH | PENDING |
| `data/reference/seoul_121_places.csv` | Data | KEEP | HIGH | CRITICAL | PENDING |
| `data/samples/population_yeouido_sample.json` | Data | KEEP | HIGH | HIGH | PENDING |
| `docs/analysis/ANALYSIS_PLAN.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `docs/history/analysis/EG5_DATA_ANALYSIS_REPORT.md` | Document | ARCHIVE_CANDIDATE | HIGH | LOW | PENDING |
| `docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/data/FIELD_DICTIONARY.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/data/MANUAL_V3_SNAPSHOT_INTAKE.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/data/ML_READY_DATASET_SPEC.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `docs/architecture/CODEX_HARNESS_ARCHITECTURE.md` | Document | MOVE_CANDIDATE | HIGH | HIGH | PENDING |
| `docs/engineering/DEVELOPMENT_WORKFLOW.md` | Document | KEEP | HIGH | MEDIUM | PENDING |
| `docs/engineering/FreshManager_TRD_v1.0.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `docs/history/research/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md` | Document | ARCHIVE_CANDIDATE | HIGH | LOW | PENDING |
| `docs/product/EG6_AREA_SPOT_PANEL.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/product/FreshManager_PRD_v1.0.md` | Document | UPDATE_REQUIRED | HIGH | HIGH | PENDING |
| `docs/history/research/PILOT_AREA_SELECTION_ASSESSMENT.md` | Document | ARCHIVE_CANDIDATE | HIGH | LOW | PENDING |
| `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/rules/CODING_RULES.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/rules/DATA_COLLECTION_RULES.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/rules/GIT_WORKFLOW.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/rules/ML_EXPERIMENT_RULES.md` | Document | KEEP | HIGH | MEDIUM | PENDING |
| `docs/rules/SECURITY_RULES.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/history/plans/2026-07-27-eg8c-ml-modeling.md` | Document | ARCHIVE_CANDIDATE | HIGH | MEDIUM | PENDING |
| `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md` | Document | KEEP | HIGH | MEDIUM | PENDING |
| `docs/testing/PROJECT_GUARD_SPEC.md` | Document | KEEP | HIGH | CRITICAL | PENDING |
| `docs/testing/QUALITY_GATES.md` | Document | KEEP | HIGH | HIGH | PENDING |
| `docs/data/DATA_COLLECTION_EXECUTION_GUIDE.md` | Document | MOVE_CANDIDATE | HIGH | MEDIUM | PENDING |
| `freshmanager/__init__.py` | Code | KEEP | HIGH | MEDIUM | PENDING |
| `freshmanager/backup.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `freshmanager/batch_id.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/collector.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/config.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/eg5.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/eg6b.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `freshmanager/eg7.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/eg8a.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/eg8b.py` | Code | KEEP | HIGH | MEDIUM | PENDING |
| `freshmanager/eg8b_b2a.py` | Code | KEEP | HIGH | MEDIUM | PENDING |
| `freshmanager/eg8b_b2b.py` | Code | KEEP | HIGH | MEDIUM | PENDING |
| `freshmanager/eg8c_features.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `freshmanager/eg8c_modeling.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/eg8d_area_priority.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/http_adapter.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/live.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `freshmanager/manual_snapshot_intake.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `freshmanager/offline.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/pilot_area_recommendation.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/pilot_recommendation_service.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/pilot_spot_options.py` | Code | KEEP | HIGH | HIGH | PENDING |
| `freshmanager/storage.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `docs/analysis/GATE_C_INTERVIEW_PLAN.md` | Document | MOVE_CANDIDATE | HIGH | MEDIUM | PENDING |
| `docs/analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md` | Document | MOVE_CANDIDATE | HIGH | HIGH | PENDING |
| `docs/history/requirements/requirements-definition-freshmanager-poc-v0.4.md` | Document | ARCHIVE_CANDIDATE | HIGH | LOW | PENDING |
| `requirements-ml.txt` | Config | KEEP | HIGH | HIGH | PENDING |
| `scripts/project_guard_check.py` | Code | KEEP | HIGH | CRITICAL | PENDING |
| `tests/fixtures/csv/missing_required_column.csv` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/eg8a/valid_population_current_v3.csv` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/eg8a/valid_population_forecast_v3.csv` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/eg8a/valid_raw_log_v3.csv` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/json/empty_forecast_array.json` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/json/forecast_missing_field.json` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/json/invalid_json.json` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/fixtures/json/missing_population_field.json` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/test_backup.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_batch_id.py` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/test_eg4_collector.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg5.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg6_reference_data.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg6b.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg7.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg8a.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg8b.py` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/test_eg8b_b2a.py` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/test_eg8b_b2b.py` | Test | KEEP | HIGH | MEDIUM | PENDING |
| `tests/test_eg8c_features.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg8c_modeling.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_eg8d_area_priority.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_http_adapter.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_live.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_manual_snapshot_intake.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_pilot_area_recommendation.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_pilot_recommendation_service.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_pilot_spot_options.py` | Test | KEEP | HIGH | HIGH | PENDING |
| `tests/test_project_guard_check.py` | Test | KEEP | HIGH | CRITICAL | PENDING |

---

Audit 범위 준수: 기존 파일 수정 0, 이동 0, 삭제 0, 코드·Dependency 변경 0,
실제 API·Recommendation·ML 실행 0이다.
