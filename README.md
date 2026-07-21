# Freshmanager Data PoC

## 1. 프로젝트 소개

이 프로젝트는 프레시매니저 유동판매 위치·시간 추천 서비스의 선행 단계인
서울시 공개데이터 기반 데이터 타당성 PoC다.

현재 단계에서는 프레시매니저가 사용하는 모바일 앱이나 추천 화면을 개발하지 않는다.

서울시 주요 121장소를 장기 공식 후보군으로 유지하되, 현재는 EG-6A에서 확정한
13개 Area 패널의 수집·분석 가능성을 먼저 검증한다. EG-6B 단일 회차 파이프라인은
`main`에 병합됐고, 실제 13개 Area 회차와 PM PASS 판정은 아직 남아 있다.

### 공식 문서 안내

새 세션은 다음 문서를 순서대로 확인한다.

1. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — 현재 단계와 다음 행동
2. [`FreshManager_PRD_v1.0.md`](docs/product/FreshManager_PRD_v1.0.md) — 공식 제품 기준
3. [`FreshManager_TRD_v1.0.md`](docs/engineering/FreshManager_TRD_v1.0.md) — 공식 기술 기준
4. [`AGENTS.md`](AGENTS.md) — Codex 작업 절차와 금지사항
5. [`CODEX_HARNESS_ARCHITECTURE.md`](docs/engineering/CODEX_HARNESS_ARCHITECTURE.md) — 문서·검증·승인 구조
6. [`DATA_COLLECTION_RULES.md`](docs/rules/DATA_COLLECTION_RULES.md) — 데이터 수집·보존 규칙
7. [`QUALITY_GATES.md`](docs/testing/QUALITY_GATES.md) — 단계 진입·통과 기준
8. [`PROJECT_GUARD_SPEC.md`](docs/testing/PROJECT_GUARD_SPEC.md) — 자동검사 기준

---

## 2. 현재 검증 목표

1. 현재 13개 Area 패널을 안정적으로 수집하고 후속 필요 시 121개로 확장할 수 있는가
2. 장소별 현재 인구값과 미래 인구예측값을 모두 저장할 수 있는가
3. 같은 미래시점의 예측값을 수집시점별로 보존할 수 있는가
4. 서울시 예측값과 후속 관측값을 비교할 수 있는가
5. 장소 유형과 요일·시간대에 따른 반복 패턴이 존재하는가
6. 인구 증가와 카드소비 기반 소비활동 변화가 함께 나타나는가
7. 수집된 데이터가 향후 프레시매니저 서비스 가설 검증에 활용 가능한가

---

## 3. 수집 범위와 분석 범위

### 장기 공식 후보군

서울시 주요 121장소. 장소코드 검증과 후속 확대의 유일한 기준은 공식 CSV다.

### 현재 MVP 구현·수집 범위

- 여의도 1개 Area: 실제 수집·검증 완료
- 대표 3개 Area: 실제 수집·분석 완료
- EG-6A 13개 Area·Spot·S-DoT 패널: 확정·`main` 반영 완료
- EG-6B 동일 13개 Area 단일 회차 파이프라인: 구현·오프라인 검증·`main` 병합 완료
- 실제 EG-6B 13개 Area 단일 회차: 미실행, 별도 PM 승인 필요

### 현재 분석 범위

- 여의도와 EG-5 대표 3개 Area
- EG-6A에서 확정한 13개 Area·Spot·S-DoT 패널
- 유동인구·혼잡·Forecast·S-DoT Feature와 스팟 이동 기회

### 후속 범위

실제 EG-6B 단일 회차와 EG-7 반복수집, EG-8 Feature 분석에서 필요성이 확인된
경우에만 별도 PM 승인으로 121개 Area 확대를 검토한다.

```text
장기 후보군: 서울시 주요 121장소
현재 MVP: 1개 Area → 대표 3개 Area → 13개 Area 패널
현재 Gate: EG-6B 구현 완료 / 실제 단일 회차·PM PASS 대기
후속 검토: EG-7·EG-8 결과 후 필요 시 121개 확대
```

### 현재 제외 범위

- 모바일 앱
- 웹 서비스 화면
- 지도 UI
- 프레시매니저 위치 추적
- 실제 판매량 수집
- 고객 개인정보 수집
- 개별 건물 또는 지하철 출구 추천
- 이동경로 최적화
- 자체 AI 예측 모델
- 머신러닝 학습
- 유료 데이터
- hy 내부 데이터 연동
- 대중교통·문화행사 데이터의 필수 연동
- 프로덕션 수준의 대규모 인프라
- 호출한도 확인 전 121장소 고빈도 자동수집
- PM 승인 없는 5분 단위 전체수집

---

## 4. 공식 장소 목록

수집기와 Project Guard가 공통으로 사용하는 유일한 공식 장소 기준파일은 다음 CSV다.

```text
data/reference/seoul_121_places.csv
```

| 상태 | 현재 값 |
|---|---|
| 공식 CSV 배치·정비 및 `main` 반영 | 완료 |
| CSV 무결성 검증 | 읽기 전용 재검증 완료 |
| EG-1 통과 | PASS |

- XLSX 파일과 XLSX 보존 경로는 사용하지 않는다.
- CSV는 Python 표준 라이브러리 `csv` 모듈로만 읽는다.
- `encoding="utf-8-sig"`를 사용해 UTF-8과 UTF-8 BOM을 모두 처리하며,
  BOM 존재 자체를 필수조건으로 요구하지 않는다.
- 공식 CSV 처리를 위해 `openpyxl`을 사용하거나 설치하지 않는다.
- 수집기와 Project Guard는 CSV를 자동 수정·보정·정렬·덮어쓰기·재인코딩하거나
  다른 형식으로 변환하지 않는다.

공식 CSV는 `CATEGORY`, `NO`, `AREA_CD`, `AREA_NM`, `ENG_NM`의 정확한
5개 컬럼과 순서, 유효 장소 121개를 기준으로 재검증해 EG-1을 통과했다.

기준 컬럼:

| 컬럼 | 의미 |
|---|---|
| `CATEGORY` | 장소 분류 |
| `NO` | 목록 순번 |
| `AREA_CD` | 서울시 장소코드 |
| `AREA_NM` | 한글 장소명 |
| `ENG_NM` | 영문 장소명 |

공식 CSV 사용 전에는 파일 존재, UTF-8 또는 UTF-8 BOM 읽기 가능 여부,
필수 컬럼, 데이터 121행, `AREA_CD` 결측·중복, `AREA_NM` 결측,
여의도 코드와 분류별 합계 121을 읽기 전용으로 확인한다.

검증 과정에서 장소코드를 생성·보정하거나 CSV 내용을 변경하지 않는다.
기준파일 변경은 PM 승인 없이 진행하지 않는다.

---

## 5. 장소코드 사용 원칙

API 호출에는 확정 경로에 배치되고 검증을 통과한 공식 CSV의
`AREA_CD`만 사용한다.

여의도 공식 장소코드:

```text
POI072
```

`POI`는 영문 대문자 `P`, `O`, `I`다.

다음 방식은 사용하지 않는다.

```text
POI001부터 POI121까지 자동 생성
```

장소코드는 중간 번호가 비어 있을 수 있으므로
공식 파일에 실제로 존재하는 코드만 사용한다.

비슷한 이름의 장소도 별도 장소로 유지한다.

예:

```text
여의도: POI072
여의도한강공원: 별도 장소코드
여의서로: 별도 장소코드
```

---

## 6. 현재 프로젝트 상태

### 완료

- 서울 열린데이터광장 일반 인증키 발급
- 공식 장소 기준 CSV 배치
- 공식 장소 기준 CSV 정비·`main` 반영 및 EG-1 통과
- EG-0 문서 기준선 PM 승인
- 공식 여의도 실응답 샘플 `data/samples/population_yeouido_sample.json` 배치
- 공식 샘플 읽기 전용 사전검증과 `H-301`~`H-304` 통과
- EG-3 Python 기반 Project Guard `scripts/project_guard_check.py` 구현 및 로컬 검증 완료
- Issue #32 EG-4 POI072 오프라인 수집기와 Fake 기반 검증 완료
- Issue #34 EG-4 HTTP Adapter와 명시적 Transport 주입의 Fake 기반 검증 완료
- Issue #39 Closed 및 PR #40 Squash Merge 완료: POI072 단일 실행 CLI와 Fake Transport 기반 오프라인 검증 `main` 반영 완료
- Issue #43에서 POI072 실제 정상 JSON과 원본·메타데이터 저장 확인, EG-4 PASS
- Issue #46·PR #48에서 대표 3개 Area 수집기 구현·병합 및 실제 3/3 수집 완료, EG-5 PASS
- Issue #51·PR #52에서 서로 다른 공식 Area 13개와 Spot·S-DoT 참조 패널 `main` 반영
- Issue #53·PR #54에서 13개 Area 단일 순차수집·Batch Log·Manifest·SHA-256 파이프라인 구현·오프라인 검증·`main` 병합
- PR #54와 병합 후 `main` CI 성공
- EG-6B Target Tests 19/19, Full Unit Tests 243/243, Project Guard PASS 41·SKIP 5·TOTAL 46
- `AGENTS.md` 생성
- Codex의 `AGENTS.md` 인식 확인

`tests/fixtures/`는 결측 필드, 잘못된 JSON, 빈 예측 배열 등 오류 테스트
입력에만 사용하며 공식 실응답 샘플을 이동·복사하지 않는다.

### 진행 예정

- 별도 PM 승인 후 EG-6B 실제 최대 13회 단일 회차 실행
- Raw·Metadata·Collection Log·Manifest·SHA-256 검토
- 실제 호출량·성공률·실패율·소요시간 확인
- PM의 EG-6B PASS 또는 보완 판정
- EG-6B PASS와 백업·주기 승인 후 EG-7 반복수집 파일럿 검토

### 미진행

- EG-6B 실제 13개 Area 단일 회차
- EG-6B 최종 PASS 판정
- EG-7 반복수집·Scheduler·자동 재시도
- EG-8 Feature 유효성 분석
- 121장소 자동수집
- 장기 데이터 누적
- 장소별 예측 성능 비교
- 카드소비 상권현황 분석
- Gate A·B·C 데이터 PoC 판정
- 모바일 서비스 개발

---

## 7. 데이터 대상

### 공식 Area 공통 필수 데이터

- 장소 분류
- 장소코드
- 장소명
- 실시간 추정 인구
- 현재 혼잡도
- 미래 인구예측
- API 요청시각
- 인구 데이터 기준시각
- 수집 성공·실패 상태

### 지원 장소에 한해 수집하는 데이터

- 카드소비 기반 실시간 상권현황

상권현황이 지원되지 않는 장소는 다음처럼 기록한다.

```text
not_supported
```

지원 장소이지만 해당 시점 데이터가 없으면 다음처럼 기록한다.

```text
missing
```

둘 다 `한산` 또는 `0`으로 바꾸지 않는다.

### 날씨 데이터

- 날씨 관측값
- 날씨 예보값

날씨 관측값과 예보값은 실제 제공 여부를 각각 기록하고,
한쪽이 없다고 다른 값으로 대체하지 않는다.

### 최소 수집 메타데이터

- `request_id`
- `area_code`
- `endpoint_name`
- `requested_at`
- `received_at`
- `http_status`
- `collection_status`
- `raw_file_path`

Issue #32 PM 결정에 따라 이전 최소 계약의 `parser_version` 대신
`received_at`을 사용한다.

`endpoint_name`에는 실제 URL이 아니라 `citydata_ppltn`과 같은 논리적 이름을 저장한다.
`raw_file_path`에는 원본 JSON 내용이 아니라 저장된 원본 파일 경로를 기록한다.

### 선택 데이터

- 대중교통 승하차
- 문화행사
- S-DoT 유동인구

선택 데이터는 PM 승인 없이 필수 범위로 추가하지 않는다.

---

## 8. API 호출 방식

서울시 API는 한 번 호출할 때 한 장소를 조회한다.

현재 EG-6B 단일 회차는 승인된 13개 Area를 다음 순서로 처리한다.

```text
검증된 공식 CSV 읽기
→ 장소 하나 호출
→ 원본 JSON 저장
→ 요청별 metadata 저장
→ 성공·실패 기록
→ 다음 장소 호출
→ 승인된 13개 Area까지 반복
→ Collection Log·Manifest·SHA-256 생성·검증
```

한 장소의 오류 때문에 전체 회차를 중단하지 않는다.

회차 종료 후 다음을 확인한다.

- 전체 대상 장소 수
- 성공 장소 수
- 실패 장소 수
- 실패 장소 목록
- 전체 소요시간

---

## 9. 단계적 구현 순서

| 엔지니어링 게이트 | 내용 | 현재 상태 |
|---|---|---|
| EG-0 | 문서 기준선 | 통과: PM 승인 완료 |
| EG-1 | 장소 기준데이터 사전검증 | 통과: 공식 CSV 정비·`main` 반영 및 읽기 전용 재검증 완료 |
| EG-2 | 샘플 JSON 사전검증 | 통과: 공식 샘플 배치 및 `H-301`~`H-304` PASS |
| EG-3 | Project Guard 구현 및 자동 재검증 | 구현·로컬 검증 완료: PASS 28, SKIP 17 |
| EG-4 | 여의도 1장소 | 통과: Issue #43 실제 POI072 정상 JSON과 원본·메타데이터 저장 확인 |
| EG-5 | 유형별 대표 3장소 | 통과: POI019·POI013·POI014 실제 수집 3/3, 재시도 0회와 구조 분석 완료 |
| EG-6A | 13개 Area·Spot·S-DoT 패널 | 통과: Issue #51·PR #52로 13개 고유 공식 Area 패널 `main` 반영 |
| EG-6B | 동일 13개 Area 단일 수집 | 진행: Issue #53·PR #54 구현·오프라인 검증·병합 완료, 실제 회차·PM PASS 대기 |
| EG-7 | 동일 13개 Area 반복수집 파일럿 | 미진행: EG-6B PASS와 주기·백업 승인 필요 |
| EG-8 | Feature 유효성 분석 | 미진행: 반복 관측 데이터 필요 |

EG-1과 EG-2는 Project Guard 구현 전의 읽기 전용 사전검증이다.
공식 여의도 실응답 샘플 경로는
`data/samples/population_yeouido_sample.json`이다.
EG-3에서 문서, 공식 CSV, 샘플 JSON을 네트워크 없이 자동 재검증한다.
일반 Project Guard와 Unit Tests는 실제 `.env`·인증키·네트워크를 사용하지 않는다.
실제 실행은 각 Gate에서 env-file·output-root·호출 수를 PM이 별도로 승인한 경우에만
일반 테스트와 분리해 진행한다.
각 게이트 통과 후 다음 구현 단계로 전환하려면 PM 승인을 받는다.

EG-0~EG-8은 구현 준비도와 엔지니어링 품질을 판정한다.
Gate A·Gate B·Gate C는 별도의 데이터 PoC 판정 게이트이며,
어떤 EG의 통과도 Gate A·B·C 통과를 의미하지 않는다.

처음부터 121장소 자동수집과 장기실행을 동시에 구현하지 않는다.

---

## 10. 수집주기 원칙

동일 13개 Area 반복수집 주기는 아직 확정하지 않았다.

다음 내용을 확인한 뒤 PM이 승인한다.

- 서울시 API 일일 호출한도
- 13개 Area 1회 수집 소요시간
- 데이터 실제 갱신주기
- 호출 성공률과 실패율
- 재시도에 따른 추가 호출량
- 운영 컴퓨터의 안정성
- 분석에 필요한 시간해상도

따라서 현재는 다음을 기본값으로 두지 않는다.

```text
5분마다 13개 Area 전체 호출
```

---

## 11. 데이터 해석 원칙

### 인구 데이터

서울시 인구값은 현장에서 직접 센 실제 인원이 아니라 추정 인구다.

사용 가능한 표현:

- 장소별 추정 인구
- 후속 시점 관측값
- 예측값과 후속 관측값의 일치도

사용하지 않는 표현:

- 정확한 실제 인구
- 현장 실측 인원
- 특정 출구의 정확한 보행량

### 상권현황

카드소비 기반 상권현황은 소비활동 대리변수다.

사용 가능한 표현:

- 카드소비 기반 소비활동 대리변수
- 상권 활동단계
- 일반 소비활동 변화

사용하지 않는 표현:

- 실제 야쿠르트 매출
- 프레시매니저 판매실적
- 실제 전체 소비금액
- 구매전환율

---

## 12. 공간 단위 해석 원칙

121장소는 서울시가 정의한 POI 영역이다.

장소별 인구값은 다음을 의미하지 않는다.

- 특정 지하철 출구의 인구
- 특정 빌딩 앞 인구
- 개별 판매지점의 보행량
- 특정 프레시매니저 담당구역 인구
- 실제 야쿠르트 구매고객 수

이름이 비슷한 장소도 임의로 합치지 않는다.

---

## 13. 원본 데이터 보존 원칙

서울시 API에서 받은 원본 JSON은 수정하지 않는다.

- 장소별 호출마다 새 파일로 저장한다.
- 기존 파일을 덮어쓰지 않는다.
- 파일명에 장소코드와 요청시각을 포함한다.
- 원본 필드명을 변경하지 않는다.
- 문자열 형태의 숫자도 원본에서는 변환하지 않는다.
- 값이 이상해 보여도 원본에서 삭제하지 않는다.
- 결측값을 임의로 `0`으로 바꾸지 않는다.
- 데이터 오류 여부는 별도 로그에 기록한다.
- 분석용 CSV에서만 형식을 변환한다.

원본 파일명 예:

```text
POI072_20260716_200000.json
```

권장 저장구조:

```text
data/raw/population/2026/07/16/POI072_20260716_200000.json
```

---

## 14. 예측 데이터 보존 원칙

미래 예측값은 최신값 하나만 남기지 않는다.

구분해야 하는 시각:

- API 요청시각
- 현재 인구 기준시각
- 예측 스냅샷 시각
- 예측 대상시각
- 후속 관측시각

같은 미래 대상시각의 예측이 여러 번 수집돼도
기존 예측값을 덮어쓰지 않는다.

공식 예측 발행시각 필드가 확인되지 않으면 임의로 만들지 않는다.

---

## 15. 날씨 데이터 원칙

날씨 관측값과 날씨 예보값은 분리 저장한다.

- 실제 관측값과 미래 예보값을 같은 CSV에 섞지 않는다.
- 예보에는 예보 발행시각과 예보 대상시각을 저장한다.
- 예측 평가에는 당시 이용 가능했던 예보값만 사용한다.
- 이후 관측된 실제 날씨를 과거 예측 입력값으로 사용하지 않는다.
- 실제 날씨는 사후 원인 분석과 예보 오차 확인에만 사용한다.
- 예보가 없다고 실제 관측값으로 대체하지 않는다.

---

## 16. API 키 관리

서울시 API 키는 비밀정보다.

실제 키는 프로젝트 루트의 `.env` 파일에만 저장하고,
`.env`는 `.gitignore`에 포함한다.

로컬 `.env`는 존재하지만 Git에서 제외돼 있다. 별도 PM 외부 실행 승인 전에는
내용을 읽거나 실제 키 존재 여부를 확인하지 않으며 실제 키를 사용하지 않는다.

실제 키를 다음 위치에 작성하지 않는다.

- Python 코드
- README
- Markdown 문서
- Git 커밋
- GitHub
- 콘솔 출력
- 오류 로그
- 인증키가 포함된 전체 URL
- 화면 캡처
- 테스트 파일

API 요청 주소를 기록할 때 인증키 부분을 마스킹한다.

```text
http://openapi.seoul.go.kr:8088/********/json/...
```

공유용 파일은 `.env.example`만 사용하고 실제 키를 넣지 않는다.

```env
SEOUL_OPEN_API_KEY=your_api_key_here
```

---

## 17. 저장 경계

- 공식 CSV·샘플·코드·문서는 Git 저장소에 둔다.
- 실제 Raw·Metadata·Collection Log·Manifest는 PM이 승인한 저장소 밖
  `output-root`에 둔다.
- EG-4·EG-5·EG-6B 결과는 단계별 하위 경로로 분리한다.
- 기존 실제 원본과 메타데이터는 자동 삭제하거나 덮어쓰지 않는다.
- `.env`는 Git 추적에서 제외하며 실제 값은 출력하지 않는다.
- 반복수집 전에는 외장 저장장치 복사 또는 PM 승인 클라우드 폴더 백업 중 하나를
  별도 Gate로 준비한다. 수집 실행 자체는 로컬 Python에 유지한다.

---

## 18. 현재 실행방법

Python 기반 Project Guard가 `scripts/project_guard_check.py`에 구현돼 있다.
PR #54 기준 최신 검증은 `PASS 41`, `FAIL 0`, `WARN 0`, `SKIP 5`,
`TOTAL 46`, 종료 코드 `0`이며 전체 Unit Tests는 243/243 PASS다.

표준 Project Guard 실행 명령:

```bash
python3 scripts/project_guard_check.py
```

단위 테스트 실행 명령:

```bash
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

일반 Project Guard와 일반 테스트는 저장된 샘플 또는 가짜 응답만 사용하며
네트워크와 실제 서울시 API를 호출하지 않는다. `freshmanager/http_adapter.py`에
실제 통신은 HTTP Adapter 안에 분리돼 있고 일반 테스트에서는 Fake Transport만
사용한다. 현재 `main`의 EG-6B CLI는 승인 패널 13개를 `panel_order` 순서로 각각
최대 한 번 처리하며 자동 재시도와 반복 실행은 없다.

공식 EG-6B 실행 명령 형식은 다음과 같다. 아래 명령은 PM이 정확한 env-file,
저장소 밖 output-root와 최대 13회 호출을 별도로 승인한 뒤에만 실행한다.
`--execute-live` 자체는 PM 승인을 의미하지 않는다.

```bash
python3 -m freshmanager.eg6b \
  --env-file /path/to/approved-local.env \
  --output-root /path/to/approved-external-output-root \
  --timeout 10 \
  --execute-live
```

현재 EG-6B 실제 단일 회차는 미실행 상태다. 실행 후 Raw·Metadata·Collection Log·
Manifest·SHA-256과 실패 목록을 검토하고 PM이 PASS 또는 보완을 판정해야 한다.

---

## 19. 작업 원칙

Codex는 작업 전 반드시 `AGENTS.md`를 읽는다.

관련 운영 문서:

- `docs/product/FreshManager_PRD_v1.0.md`: 공식 제품 목적·범위·수용 기준
- `docs/engineering/FreshManager_TRD_v1.0.md`: 공식 기술 구조·계약
- `PROJECT_STATUS.md`: 현재 단계와 다음 행동
- `docs/engineering/CODEX_HARNESS_ARCHITECTURE.md`: 문서·검증·승인 책임 구조
- `docs/rules/GIT_WORKFLOW.md`: Git 작업 운영 규칙
- `docs/rules/SECURITY_RULES.md`: 보안 운영 규칙
- `docs/rules/DATA_COLLECTION_RULES.md`: 데이터 수집·원본 보존·결측 처리 규칙
- `docs/data/FIELD_DICTIONARY.md`: 원본·정규화·메타데이터·파생필드 정의
- `docs/analysis/ANALYSIS_PLAN.md`: 분석 질문·기준선·평가기간·Gate 판정 계획
- `.github/ISSUE_TEMPLATE/task.md`: 범용 작업 Issue 템플릿
- `.github/pull_request_template.md`: Pull Request 검토 템플릿

```text
요구사항 확인
→ 현재 EG와 선행 게이트 확인
→ 읽기 전용 사전검증 또는 적용 Project Guard 검사
→ 게이트 판정
→ PM의 다음 구현 단계 전환 승인
→ 승인된 최소 단위 구현
→ 결과 보고
```

위 흐름은 구현 작업에 적용한다.
문서 전용 작업은 Python 기반 Project Guard를 새로 만들지 않는다. 기존 H-001~H-004
입력 문서를 바꾸거나 PM이 요구한 경우에는 구현된 Project Guard와 승인된 테스트를
실행하고, 모든 문서에서 코드 블록·Markdown 제목·링크·규칙·상태 일관성을 확인한다.

검사 실행과 읽기 전용 판정 자체에는 PM 승인이 필요하지 않다.
다음 작업은 PM 명시 승인 후 진행한다.

- 품질 게이트 통과 후 다음 구현 단계로의 전환
- 실제 서울시 API 호출
- 새로운 패키지 또는 라이브러리 설치
- 기준파일 생성·배치·교체·변경
- 데이터 저장구조 변경
- API 호출주기 결정 또는 변경
- 자동실행 구성 또는 변경
- GitHub main 브랜치 병합

EG-1과 EG-2는 Project Guard 없이 읽기 전용으로 판정하고,
EG-3부터 적용 대상 Project Guard 검사를 사용한다. 121개 Area 확대는 현재 13개
패널의 단일·반복 수집과 Feature 분석에서 필요성이 확인된 경우에만 별도 승인한다.

---

## 20. 완료 기준

구현 작업은 현재 EG에 적용되는 다음 조건을 모두 만족해야 완료로 판단한다.
후속 EG에서만 적용되는 조건을 현재 단계의 선행 완료조건으로 요구하지 않는다.
단계별 세부조건은 `docs/testing/QUALITY_GATES.md`를 따른다.

- 무결성 검증을 통과한 공식 CSV 121행을 읽음
- 공식 CSV의 실제 장소코드만 사용함
- 모든 장소의 성공·실패 상태를 기록함
- 한 장소 실패로 전체 수집이 중단되지 않음
- 장소별 원본 JSON을 저장함
- 기존 원본 파일을 덮어쓰지 않음
- 예측 스냅샷을 덮어쓰지 않음
- 상권 미지원과 결측을 구분함
- API 키가 노출되지 않음
- Project Guard 검사를 실행하고 통과함
- 현재 품질 게이트 통과와 다음 단계 전환 승인을 구분함
- 실행방법을 한국어로 설명함
- PM 확인사항과 남은 위험을 보고함

문서 전용 작업은 다음을 모두 만족해야 완료로 판단한다.

- 요청받은 문서만 수정함
- 코드 블록 정상 종료와 Markdown 제목 구조를 확인함
- 프로젝트 목표, 수집 범위, 분석 범위가 일치함
- 공식 CSV 경로와 배치·검증·EG-1 상태가 일치함
- 단계적 구현 순서와 호출주기 원칙이 일치함
- Gate A·B·C와 EG-* 명칭이 구분됨
- 검사 ID 중복·누락과 품질 게이트 순환 여부를 확인함
- 상권 상태와 API 키 보안 규칙이 일치함
- 원본·예측·날씨 규칙이 일치함
- 완료·미완료 상태와 여섯 문서 사이의 충돌 여부를 확인함
- PM 확인사항과 남은 위험을 보고함

PM 최종 승인 전에는 작업을 최종 완료로 확정하지 않는다.
