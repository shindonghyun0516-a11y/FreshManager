# EG-8C ML Modeling Implementation Plan

> **현재 상태 안내(2026-07-29):** 이 문서는 당시 승인된 구현 계획을 보존하는
> 이력문서다. 아래 Ridge 자동 탐색 계획은 Issue #120·PR #121의 최신 PM 결정으로
> 대체됐으며, 신규 공식 데이터 재평가는 `alpha=100.0` 고정·자동 탐색 없이 실행됐다.
> 최종 판단은 `BASELINE_RETAINED`이며 상세 결과는 Issue #119를 따른다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 잠긴 EG-8C Run #2 Dataset으로 현재 인구 Baseline, 서울시 Forecast Baseline, Linear Regression, Ridge Regression을 동일한 Validation 행에서 비교하는 잠정 인구 중간값 회귀를 구현한다.

**Architecture:** 기존 EG-8C Dataset 8개는 읽기 전용으로 검증하고 `row_id`로 Feature·Label·Split을 결합한다. 전처리와 Ridge 조정은 TRAIN에만 맞추며, VALIDATION은 최종 비교에 한 번만 사용한다. 결과는 호출자가 지정한 새 Modeling Output Root에 1회성 파생 산출물로 기록하고 기존 Dataset이나 공식 Run Root는 수정하지 않는다.

**Tech Stack:** PM이 승인한 Python 3.12 격리환경, 표준 라이브러리(`csv`, `json`, `hashlib`, `pathlib`, `statistics`)와 `requirements-ml.txt`에 고정한 `scikit-learn==1.6.1`.

**Plan Status:** `EG8C_ML_MODELING_PLAN_READY_FOR_IMPLEMENTATION`

## Global Constraints

- 이 문서는 구현 계획이다. 이 단계에서는 코드, Training Matrix, 모델 산출물, Dependency를 생성하거나 학습을 실행하지 않는다.
- 기준 Dataset은 Run ID `eg8c-20260727T153257-kst`, Manifest SHA-256 `388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771`로 고정한다.
- 기준 Split은 `TRAIN=1742`, `VALIDATION=416`, `EXCLUDED=78`이며 재분할·셔플·Test Split 생성을 금지한다.
- `evaluation_status=PROVISIONAL`, `data_sufficiency_status=PROVISIONAL_SPLIT_ONLY`, `test_split_created=false`, `official_model_gate_judgment=null`을 유지한다.
- 기존 Feature 28개와 `label_value` 계약을 변경하지 않는다. 누락값을 자동 보정하거나 새 Feature를 파생하지 않는다.
- 현재 Label 계약에는 `peak_flag`가 없으므로 이번 구현은 `target_population_midpoint` 회귀만 다룬다. 피크 예측과 EG-8C 최종 Gate 통과 주장은 별도 Dataset/Label 승인 전까지 제외한다.
- 실제 구현은 새 Issue·Branch·Worktree와 PM 승인 범위에서만 시작한다. ML Runtime과 Dependency는 아래 승인 Profile을 따른다.
- Dataset 원본, 공식 Run #1·#2, Manifest, Contract, Evidence는 읽기 전용으로 유지한다.

---

## PM Decision Record

- 결정일: 2026-07-27
- 선택안: Option 1
- 성공 기준: 가장 강한 Baseline보다 VALIDATION 전체 MAE가 낮고 RMSE가 악화되지 않은 ML 후보를 잠정 우승 모델로 기록한다.
- 공식 채택: Test Split과 추가 장기 데이터 확보 후 별도 Model Gate에서 판단한다.
- 유지 상태: `evaluation_status=PROVISIONAL`, `official_model_gate_judgment=null`.

## Approved ML Runtime Profile

- Python 3.12 격리 가상환경과 `requirements-ml.txt`의 `scikit-learn==1.6.1`을 사용한다.
- 전체 전이 Dependency Lock은 현재 PoC 범위에서 만들지 않고, 실제 설치 버전은 `model_metadata.json`에 기록한다.
- Modeling Output Root는 `FRESHMANAGER_ML_OUTPUT_ROOT` 환경변수로 주입하며 Dataset Root와 Git 추적 경로를 금지한다.
- 로컬 Output Root는 저장소 외부 경로, CI 검증은 Runner 임시 경로만 사용한다.
- Modeling Run ID 형식은 `eg8c-ml-YYYYMMDDTHHMMSS-kst`이며 Run마다 새 디렉터리를 만들고 기존 Run 덮어쓰기와 같은 ID 재사용을 금지한다.
- Run ID와 생성시각은 `model_metadata.json`에 기록한다.

## ML 목표 정의

- 60분·180분 뒤의 `target_population_midpoint`를 예측하는 잠정 회귀 모델을 만든다.
- 현재 인구 유지값과 서울시 기존 Forecast보다 ML이 같은 VALIDATION 행에서 일관되게 나은지 판단한다.
- 결과는 모델 공식 채택이 아니라 후속 데이터 축적·Test 평가로 진행할 후보를 고르는 근거로 사용한다.
- 현재 Label에 없는 피크 여부·피크 시각 예측은 수행하지 않는다.

## Confirmed Data Contract

| 항목 | 고정 계약 |
|---|---|
| Dataset | `official-runs/<run-id>/phase-eg8c-v1/`의 검증된 8개 파일 |
| Candidate / Eligible | 2,236 / 2,158 |
| Split | TRAIN 1,742 / VALIDATION 416 / EXCLUDED 78 |
| Area / Horizon | 13개 Area / 60분 1,118행 / 180분 1,118행 |
| X | 아래 승인 Feature 28개 |
| y | `label_value` |
| Label name | `target_population_midpoint` |
| Label 정의 | `(target_population_min + target_population_max) / 2` |
| 기준 시각 | Feature는 `prediction_origin_at`까지, Label은 같은 Area의 `prediction_target_at` |

### 승인 Feature 28개

1. `area_code`
2. `horizon_minutes`
3. `hour`
4. `minute`
5. `day_of_week`
6. `is_weekend`
7. `hour_sin`
8. `hour_cos`
9. `day_of_week_sin`
10. `day_of_week_cos`
11. `current_population_min`
12. `current_population_max`
13. `current_population_midpoint`
14. `current_population_interval_width`
15. `current_congestion_level`
16. `population_lag_5m`
17. `population_lag_15m`
18. `population_lag_30m`
19. `population_lag_60m`
20. `population_delta_5m`
21. `population_delta_15m`
22. `population_delta_30m`
23. `population_delta_60m`
24. `rolling_mean_15m`
25. `rolling_mean_30m`
26. `rolling_mean_60m`
27. `rolling_std_30m`
28. `rolling_std_60m`

`row_id`, `source_collection_run_id`, `prediction_origin_at`, `prediction_target_at`, `feature_valid`, `feature_missing_reason`은 결합·감사·검증용이며 X에서 제외한다.

## Modeling Decisions

### 목표와 Baseline

- B0 Current Population Baseline: `prediction_origin_at`의 `current_population_midpoint`를 예측값으로 사용한다.
- B1 Existing Forecast Baseline: 잠긴 Forecast 입력에서 동일 `source_collection_run_id + area_code + prediction_origin_at + prediction_target_at`에 대응하는 `forecast_population_min/max` 중간값을 사용한다.
- B1은 각 평가 행에 정확히 한 건이 연결되어야 한다. 미일치·중복은 행 삭제가 아니라 전체 실행 실패다.
- ML 후보는 `LinearRegression`과 `Ridge` 두 개만 구현한다. 추가 모델은 잔차 분석에서 선형 모델의 구조적 한계가 확인된 뒤 별도 계획으로 검토한다.

### Feature 처리

- `area_code`, `current_congestion_level`: `OneHotEncoder(handle_unknown="ignore")`.
- `is_weekend`: Boolean을 0/1로 변환한다.
- 나머지 수치 Feature: `StandardScaler`.
- Encoder와 Scaler는 TRAIN으로만 `fit`하고 VALIDATION에는 `transform`만 수행한다.
- 승인 Feature 28개 중 하나라도 TRAIN 또는 VALIDATION에서 누락되면 자동 채움 없이 실패한다.
- 전처리 결과는 메모리 Pipeline에만 두며 잠긴 Feature Dataset을 변경하지 않는다.

### Label 검증

- 모든 TRAIN·VALIDATION 행에서 `label_name=target_population_midpoint`, `label_valid=true`, 유한한 `label_value`를 요구한다.
- `row_id`, Area, `prediction_origin_at`, `prediction_target_at`, `horizon_minutes`가 Feature 행과 정확히 일치해야 한다.
- Label은 같은 Area의 Target 시점 Current 인구 최소·최대 중간값이어야 하며 Feature 값에서 다시 계산하거나 대체하지 않는다.

### Model 조정

- Linear Regression은 추가 Hyperparameter 조정 없이 학습한다.
- Ridge의 `alpha` 후보는 `0.1`, `1.0`, `10.0`, `100.0`으로 고정한다.
- Ridge 선택은 TRAIN의 `prediction_origin_at` 그룹을 시간순으로 나눈 3개 expanding fold에서만 수행한다.
- 같은 `prediction_origin_at` 그룹을 서로 다른 fold로 나누지 않으며 무작위 셔플을 사용하지 않는다.
- VALIDATION은 Ridge alpha 선택이나 전처리 적합에 사용하지 않는다.

### Validation 전략과 Leakage 방지

- 잠긴 TRAIN/VALIDATION row 집합과 시간 경계를 그대로 사용하고 EXCLUDED는 어느 계산에도 포함하지 않는다.
- 모든 Baseline과 ML 후보는 동일한 VALIDATION `row_id` 집합에서 비교한다.
- Feature timestamp가 origin 이후이거나 Label target이 origin 이전인 행, 미래 실제값·사후 통계가 Feature에 들어간 행은 실행 전에 차단한다.
- 잠긴 `leakage_report.json`의 공식 12개 검사, `violation_count=0`, `final_verdict=PASS`를 입력 Gate로 확인한다.
- VALIDATION 결과를 보고 모델·판정 규칙을 다시 조정하지 않는다. 변경이 필요하면 새 계획과 새 평가 경계를 승인받는다.

### Metric과 잠정 판정

- Primary metric: VALIDATION 전체 MAE.
- Secondary metric: VALIDATION 전체 RMSE.
- Auxiliary metric: VALIDATION Median Absolute Error. 보조 설명에만 사용하고 성공 Gate에는 사용하지 않는다.
- 필수 세부 보고: 전체·60분·180분 Horizon별 MAE/RMSE/Median Absolute Error, Area별 세 지표, 평가 행 수.
- 비교 기준인 가장 강한 Baseline은 B0와 B1 중 VALIDATION 전체 MAE가 더 낮은 쪽이다. MAE가 같으면 RMSE가 더 낮은 쪽을 사용한다.
- ML 후보의 잠정 통과 조건은 모두 충족해야 한다.
  1. 전체 MAE가 비교 기준 Baseline보다 낮다.
  2. 전체 RMSE가 비교 기준 Baseline보다 나쁘지 않다.
- 두 ML 후보가 모두 통과하면 전체 MAE가 낮은 후보를 잠정 우승으로 기록한다. 동률이면 더 단순한 Linear Regression을 선택한다.
- 어떤 후보도 통과하지 않으면 가장 좋은 Baseline을 유지한다.
- Evaluation Report에는 Baseline 대비 개선 여부, 잠정 우승 모델, 데이터·평가 한계점을 함께 기록한다.
- 이 규칙은 Dataset 기반 잠정 성능 비교 기준이다. 공식 모델 채택은 Test Split과 추가 장기 데이터가 확보된 뒤 별도 Model Gate에서 판단하며 `official_model_gate_judgment`는 `null`로 유지한다.

### Training Matrix

- `feature_dataset.csv`, `label_dataset.csv`, `split_assignment.csv`를 `row_id`의 정확한 1:1:1 inner join으로 결합한다.
- 중복 `row_id`, 누락 연결, Area·origin·target·horizon 불일치는 실패한다.
- TRAIN과 VALIDATION만 Matrix에 포함하며 EXCLUDED는 절대 학습·평가에 넣지 않는다.
- 감사 가능한 파생 Matrix 컬럼은 `row_id`, `split`, 승인 X 28개, `label_value`로 한정한다.
- 인코딩·Scaling 후의 확장 컬럼은 파일로 저장하지 않고 학습 Pipeline 내부에만 둔다.

### Artifact 계약

성공한 1회 Modeling Run은 호출자가 지정한 비어 있는 Output Root 아래 새 Run ID에 다음 다섯 파일만 생성한다.

1. `training_matrix.csv`: 원시 승인 X 28개, `label_value`, `row_id`, `split`.
2. `validation_predictions.csv`: VALIDATION의 `row_id`, 실제값, B0·B1·Linear·Ridge 예측값.
3. `model_metadata.json`: Dataset Run ID, Manifest SHA, Feature 목록, Label 계약, 전처리, 모델 파라미터, 선택된 Ridge alpha, 환경 버전.
4. `evaluation_report.json`: 전체·Horizon·Area별 행 수와 MAE/RMSE/Median Absolute Error, Baseline 개선 여부, 잠정 우승 모델, 한계점, 공식 채택 미판정 상태.
5. `modeling_manifest.json`: 앞의 네 파일명·크기·SHA-256과 Source Dataset Manifest SHA.

직렬화 모델(`pickle`, `joblib`)은 생성하지 않는다. 재사용 요구와 안전한 모델 배포 계약이 승인될 때 추가한다. 기존 경로 덮어쓰기를 금지하고, 실패 시 현재 Staging만 정리하며, 성공 시 새 Run Root를 원자적으로 공개한다.

---

## File Map for the Implementation Phase

| 파일 | 작업 | 이유 |
|---|---|---|
| `freshmanager/eg8c_modeling.py` | 생성 | 잠긴 Dataset 검증, Matrix, Baseline, 전처리, 학습, 평가, Artifact 출력을 한 모듈에 둔다. |
| `tests/test_eg8c_modeling.py` | 생성 | 합성자료로 계약·시간 분할·Leakage·평가·출력 실패경계를 검증한다. |
| `requirements-ml.txt` | 생성 | PM 승인된 `scikit-learn==1.6.1` 한 개만 고정한다. |
| `.github/workflows/ml-runtime.yml` | 생성 | ML 관련 경로에서만 Python 3.12와 승인 Dependency를 검증한다. |
| `docs/analysis/ANALYSIS_PLAN.md` | 수정 | 잠정 인구 회귀 범위, 비교 규칙, 공식 채택 미판정을 기록한다. |
| `PROJECT_STATUS.md` | 구현·검증 후 수정 | 구현/실행 상태와 다음 PM Gate를 실제 결과에 맞춘다. |

별도 공통 Framework, Model Registry, Hyperparameter 설정 계층, pandas 의존성은 만들지 않는다.

---

## Task 0: PM Gates Before Implementation

**Files:** Modify this Plan; Create `requirements-ml.txt`; Create `.github/workflows/ml-runtime.yml`.

- [x] 이 계획과 Option 1 잠정 Metric 판정 규칙에 대한 PM Scope Approval을 받았다.
- [x] 새 Issue, Branch, Worktree를 만들 범위를 승인받았다.
- [x] Python 3.12 격리환경, `scikit-learn==1.6.1` 설치와 `requirements-ml.txt` 추가를 승인받았다.
- [x] `FRESHMANAGER_ML_OUTPUT_ROOT`와 `eg8c-ml-YYYYMMDDTHHMMSS-kst` Run ID 규칙을 승인받았다.
- [x] 전체 전이 Lock 제외와 실제 설치 버전의 Artifact metadata 기록을 승인받았다.

## Task 1: Locked Dataset Loader and Contract Gate

**Files:** Create `freshmanager/eg8c_modeling.py`; Create `tests/test_eg8c_modeling.py`.

- [ ] `test_locked_manifest_sha_must_match`를 먼저 작성해 잘못된 Manifest SHA에서 실패시킨다.
- [ ] `test_locked_dataset_requires_exact_eight_files_and_hashes`를 작성해 누락·추가·Hash 불일치에서 실패시킨다.
- [ ] `test_locked_contract_requires_run_counts_and_statuses`를 작성해 Run ID, Split 수, 28 Feature, Label, 잠정 정책값을 검증한다.
- [ ] 최소 Loader를 구현해 Manifest와 8개 산출물을 읽기 전용으로 확인한다.
- [ ] 다음 대상 시험을 실행해 PASS를 확인한다.

```bash
python3 -m unittest tests.test_eg8c_modeling.LockedDatasetContractTests
```

- [ ] Dataset 8개와 Manifest의 실행 전 SHA를 기록하고 구현 과정에서 변경하지 않는다.

## Task 2: Training Matrix and Two Baselines

**Files:** Modify `freshmanager/eg8c_modeling.py`; Modify `tests/test_eg8c_modeling.py`.

- [ ] `test_training_matrix_is_exact_row_id_join`을 작성해 중복·누락·식별자 불일치를 재현한다.
- [ ] `test_training_matrix_uses_28_features_and_locked_splits`를 작성해 X 목록과 `1742/416/78` 계약을 검증한다.
- [ ] `test_current_population_baseline_uses_origin_midpoint`를 작성한다.
- [ ] `test_existing_forecast_baseline_requires_one_exact_source_match`를 작성해 중복·미일치가 fail-closed인지 검증한다.
- [ ] 기존 `freshmanager/eg8b_b2b.py`의 B0/B1 정의와 `freshmanager/eg8b_b2a.py`의 Metric 계산 계약을 재사용하거나 동일 함수로 연결한다. 같은 계산을 새로 복제하지 않는다.
- [ ] `row_id` 결합과 두 Baseline을 최소 구현한다.
- [ ] 다음 대상 시험을 실행해 PASS를 확인한다.

```bash
python3 -m unittest tests.test_eg8c_modeling.TrainingMatrixTests tests.test_eg8c_modeling.BaselineTests
```

## Task 3: Train-only Preprocessing and Models

**Files:** Use approved `requirements-ml.txt`; Modify `freshmanager/eg8c_modeling.py`; Modify `tests/test_eg8c_modeling.py`.

- [ ] Task 0에서 고정한 `requirements-ml.txt`를 Python 3.12 격리환경에 설치한다.
- [ ] `test_preprocessing_fits_train_only`를 작성해 VALIDATION 값이 Encoder·Scaler 적합에 들어가지 않는지 검증한다.
- [ ] `test_missing_approved_feature_fails_without_imputation`을 작성한다.
- [ ] `test_ridge_alpha_uses_three_expanding_origin_folds`를 작성해 시간 순서, origin 그룹 보존, alpha 후보 고정을 검증한다.
- [ ] `ColumnTransformer`와 `Pipeline`으로 승인 전처리·Linear·Ridge를 최소 구현한다.
- [ ] 다음 대상 시험을 실행해 PASS를 확인한다.

```bash
python3 -m unittest tests.test_eg8c_modeling.PreprocessingTests tests.test_eg8c_modeling.ModelTrainingTests
```

## Task 4: Validation Metrics and Provisional Selection

**Files:** Modify `freshmanager/eg8c_modeling.py`; Modify `tests/test_eg8c_modeling.py`.

- [ ] `test_mae_rmse_and_median_absolute_error_match_known_fixture`를 작성한다.
- [ ] `test_all_candidates_use_identical_validation_row_ids`를 작성한다.
- [ ] `test_selection_requires_mae_improvement_and_nonworse_rmse`를 작성한다.
- [ ] `test_horizon_metrics_are_reported_but_not_used_as_success_gate`를 작성한다.
- [ ] `test_failed_candidates_retain_best_baseline_and_null_official_gate`를 작성한다.
- [ ] 기존 EG-8B Metric 함수를 재사용해 전체·Horizon·Area별 결과와 잠정 선택 규칙을 구현한다.
- [ ] 다음 대상 시험을 실행해 PASS를 확인한다.

```bash
python3 -m unittest tests.test_eg8c_modeling.EvaluationTests
```

## Task 5: Immutable Modeling Artifacts

**Files:** Modify `freshmanager/eg8c_modeling.py`; Modify `tests/test_eg8c_modeling.py`.

- [ ] `test_success_writes_exactly_five_artifacts_with_matching_manifest`를 작성한다.
- [ ] `test_existing_modeling_run_is_never_overwritten`를 작성한다.
- [ ] `test_failure_removes_current_staging_only`를 작성한다.
- [ ] `test_source_dataset_hashes_are_unchanged`를 작성한다.
- [ ] 호출자가 명시한 Output Root·Run ID에 한해 Staging 작성, Hash Manifest 생성, 배타적 원자 Rename을 구현한다.
- [ ] 오류 메시지는 Dataset 행, 전체 로컬 경로, 내부 예외 원문을 노출하지 않도록 제한한다.
- [ ] 다음 대상 시험을 실행해 PASS를 확인한다.

```bash
python3 -m unittest tests.test_eg8c_modeling.ModelingArtifactTests
```

## Task 6: Documentation and Repository Validation

**Files:** Modify `docs/analysis/ANALYSIS_PLAN.md`; Modify `PROJECT_STATUS.md`; verify all implementation files.

- [ ] `ANALYSIS_PLAN.md`에 인구 중간값 회귀만 구현됨, 두 Baseline, Metric, 잠정 선택 규칙, 피크 예측 제외, 공식 모델 미채택을 기록한다.
- [ ] `PROJECT_STATUS.md`는 실제 구현·시험 결과만 기록하고 모델 성능이나 EG-8C 완료를 선행 주장하지 않는다.
- [ ] Targeted modeling 시험을 실행한다.

```bash
python3 -m unittest tests.test_eg8c_modeling
```

- [ ] EG-8C 전체 시험을 실행한다.

```bash
python3 -m unittest tests.test_eg8c_features
```

- [ ] 저장소 전체 시험과 Project Guard를 실행한다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/project_guard_check.py
git diff --check
```

- [ ] 허용 변경파일, 의존성 한 개, Dataset SHA 불변, 실제 Dataset 학습 미실행 여부를 확인한다.
- [ ] 실제 학습 실행은 별도 PM Live/Execution Approval 전까지 수행하지 않는다.

---

## Verification Checklist for Completion

- [ ] 실제 생산 Loader 경로가 잠긴 Run ID와 Manifest SHA를 검증한다.
- [ ] X는 승인된 28개뿐이고 y는 `label_value`뿐이다.
- [ ] TRAIN/VALIDATION/EXCLUDED 수와 row 집합이 Dataset Lock과 일치한다.
- [ ] 모든 Baseline과 모델이 정확히 같은 VALIDATION `row_id`를 평가한다.
- [ ] VALIDATION이 전처리 적합이나 Ridge alpha 선택에 사용되지 않는다.
- [ ] Leakage 12종 PASS 계약과 `violation_count=0`을 입력 Gate로 요구한다.
- [ ] 잠정 우승과 공식 모델 채택을 구분하고 `official_model_gate_judgment=null`을 유지한다.
- [ ] 모델 직렬화, Test Split, Dataset 수정, 자동 재실행이 없다.
- [ ] Modeling Artifact는 새 경로에만 생성되고 기존 Run은 불변이다.
- [ ] Targeted, EG-8C, 전체 시험, Project Guard, `git diff --check`가 모두 PASS다.

## Execution Handoff

PM 승인 후 새 구현 세션에서 다음 중 하나로 실행한다.

1. **권장:** `subagent-driven-development`로 Task 0~6을 순서대로 수행하고 Task마다 검토한다.
2. **대안:** `executing-plans`로 같은 Task를 체크포인트 단위로 수행한다.

두 방식 모두 이 문서의 승인된 Task 0 Runtime Profile이 검증되기 전에는 모델 코드 작성이나 Dataset 학습을 시작하지 않는다.
