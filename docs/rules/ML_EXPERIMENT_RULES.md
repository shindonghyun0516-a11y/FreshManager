# ML Experiment Rules

- 문서 상태: Draft
- 버전: v0.1.0
- 적용 범위: Dataset Lock 이후의 Offline ML Experiment
- 상위 통제 체계: FreshManager Codex Engineering Harness
- 변경 시 PM 승인: 필요

---

## 1. 목적과 책임 경계

이 문서는 잠긴 Dataset으로 ML Experiment를 수행할 때 지켜야 하는 공통 불변
규칙을 정의한다. Harness의 작업 생명주기와 승인·검증 절차를 대체하지 않는다.

이 문서가 소유하는 범위는 Dataset Lock 이후 진입, Modeling Run, Dataset 불변,
Feature·Label·Split 사용, Leakage 방지, Baseline 비교, Validation 판단과 잠정
Model Decision이다.

Issue·Branch·PR·CI·Merge와 PM 승인 절차는
`docs/architecture/CODEX_HARNESS_ARCHITECTURE.md`,
`docs/engineering/DEVELOPMENT_WORKFLOW.md`와 `docs/rules/GIT_WORKFLOW.md`가 소유한다.
이 문서는 해당 절차의 승인 결과만 진입조건으로 참조한다. Dataset Schema는
`docs/data/ML_READY_DATASET_SPEC.md`가, EG-8C Gate는
`docs/testing/QUALITY_GATES.md`가 소유한다.

## 2. Experiment 진입 조건

ML Experiment는 다음 조건을 모두 만족한 뒤 시작한다.

- 사용할 Dataset의 Lock과 Manifest 무결성이 확인됐다.
- Feature·Label·Split과 Leakage 결과가 Dataset Lock과 일치한다.
- 사용할 Dataset, Feature, Label, Split, Baseline, Model 후보, Metric과 성공조건을
  명시한 Modeling Plan을 PM이 승인했다.

하나라도 확인되지 않으면 Training Matrix 생성이나 Model Training을 시작하지 않는다.

## 3. Modeling Run

Modeling Run은 하나의 잠긴 Dataset과 하나의 승인된 Modeling Plan으로 수행하는
단일 잠정 성능 비교 단위다.

- Dataset, Feature, Label, Split, Baseline, Metric과 성공조건은 Run 안에서 바꾸지 않는다.
- 고정 조건을 변경하려면 별도 Modeling Run으로 다시 평가한다.
- Source Dataset Run과 Modeling Run을 같은 개념으로 취급하지 않는다.

개별 Run ID, 모델 파라미터와 산출물 형식은 Modeling Plan이 관리한다.

## 4. Dataset·Feature·Label·Split

- 잠긴 Dataset과 Manifest를 수정·대체·덮어쓰지 않는다.
- Feature·Label·Split은 `docs/data/ML_READY_DATASET_SPEC.md`의 계약을 따른다.
- 승인된 Feature와 하나의 Target Label만 모델 입력에 사용한다.
- 추적·판정 목적 컬럼은 모델 입력에서 제외한다.
- TRAIN·VALIDATION·EXCLUDED 행 집합을 변경하거나 임의로 다시 나누지 않는다.
- EXCLUDED 행은 학습과 평가에 사용하지 않는다.
- Test Split을 새로 만들지 않는다.
- Training Matrix는 잠긴 Dataset에서 만든 파생 입력이며 새로운 Dataset 정본이 아니다.

## 5. Leakage 방지

- 예측 기준시각 이후의 값, 미래 관측값과 사후 통계를 Feature로 사용하지 않는다.
- 전처리 적합, Feature 선택과 Model 조정은 TRAIN 내부에서만 수행한다.
- Validation 통계와 Label을 TRAIN 전처리나 Model 선택 입력으로 사용하지 않는다.
- Baseline과 Model은 동일한 Validation 행과 Label로 평가한다.
- Leakage 위반이 확인되면 해당 Run 결과를 성능 근거로 사용하지 않는다.

## 6. Baseline·Validation 판단

- Baseline 정의와 평가 방법론은 `docs/analysis/ANALYSIS_PLAN.md`를 따른다.
- Modeling Plan에 승인된 Baseline을 Model과 함께 비교한다.
- Baseline과 Model의 Validation 행이 다르면 개선 여부를 판정하지 않는다.
- 승인된 Metric, 평가 행 수와 Baseline 대비 차이를 기록한다.
- 계산할 수 없는 Metric이나 누락 행을 0으로 대체하지 않는다.
- 데이터 기간·대표성 등 Validation 한계를 결과와 함께 기록한다.

## 7. Provisional Model Decision

Validation 성공조건을 충족한 Model은 **잠정 우승 모델**로만 기록할 수 있다.
충족하는 Model이 없으면 가장 강한 Baseline을 유지하거나 Model 판단을 보류한다.

잠정 판단은 공식 Model Gate 통과, 공식 Model 채택 또는 Production 사용 승인이
아니다. 공식 판단과 다음 단계 전환은 `docs/testing/QUALITY_GATES.md`에 따른 별도
PM 승인이 필요하다.

## 8. 비소유 범위와 문서 관리

이 문서는 Dependency 변경 절차, Runtime 운영, Artifact Publish·Backup·삭제,
Model Registry, Serving, Monitoring, Deployment와 Rollback을 정의하지 않는다.
해당 작업이 필요하면 Harness와 관련 정본에서 별도 범위와 승인을 정한다.

Experiment 결과를 잠긴 Dataset Root에 추가하거나 Dataset 산출물로 표현하지 않는다.
결과의 저장 위치·파일명·재현 정보는 승인된 Modeling Plan이 관리한다.

특정 Run ID, SHA, 행 수, 성능값과 현재 상태는 이 문서에 기록하지 않는다.
Production ML이 실제 제품 범위가 되기 전에는 운영 규칙을 이 문서에 추가하지 않는다.

| 버전 | 날짜 | 변경 내용 | 상태 |
|---|---|---|---|
| v0.1.0 | 2026-07-27 | 기존 ML Modeling Workflow Draft를 ML Experiment 공통 불변 규칙으로 경량화 | Draft |
