# Handdrawn Longform HTML

긴 분량의 한글/영문 글(설교, 에세이, 칼럼, 강연 등)의 구조와 논지를 분석하여, 일상적이고 친근한 손그림 캐릭터 중심의 슬라이드로 구성하고 정적 **HTML** 및 인쇄용 **PDF** 덱으로 렌더링하는 에이전트 스킬 엔진입니다.

## 지침 계층 구조

[`SKILL.md`](SKILL.md)는 워크플로우 실행 입구(Entry Point)입니다. [`references/`](references/) 디렉터리 하위의 문서들은 세부 처리 프로세스 및 품질 검수 참조용 지침입니다:

- `editorial-analysis.md` — 주제문 및 논지/주장 그래프 모델링 지침
- `outline-schema.md` — 슬라이드 아웃라인 및 `deck.json` 스키마 규격
- `rendering.md` — HTML/PDF 렌더링 기능 및 레이아웃 사전 검증(Preflight) 수칙
- `source-and-citation.md` — 근거, 출처 및 인용 구분 수칙
- `character-continuity.md` — 캐릭터 앵커 및 장면 일관성 지침
- `genre-adapters.md` — 설교, 에세이, 칼럼, 강의 등 장르별 변환 어댑터
- `review-checklist.md` — 최종 검수 수칙 및 자체 평가 관문

하위 참조 문서들은 독립된 스킬로 실행되지 않으며, [`SKILL.md`](SKILL.md)에 정의된 워크플로우에 따라 필요한 시점에 순차적으로 참조됩니다.

## 실행 명령

Node.js 의존성을 설치합니다:

```sh
npm install
```

경량 파이썬 검사를 실행합니다:

```sh
npm test
```

검증을 통과한 덱의 아웃라인을 확인하고 **HTML** 및 **PDF** 결과물을 빌드합니다. `--allow-overwrite` 플래그가 없으면 기존 출력 파일을 덮어쓰지 않습니다.

```sh
python3 scripts/validate_outline.py output/<slug>/deck.json
python3 scripts/build_deck.py output/<slug>/deck.json \
  -o output/<slug>/<slug>-html --targets html,pdf
```

개별 어댑터도 직접 호출할 수 있습니다:

```sh
npm run build:html -- output/<slug>/deck.json -o output/<slug>/<slug>.html
npm run build:pdf -- output/<slug>/<slug>.html -o output/<slug>/<slug>.pdf
```

`pdf` 변환을 위해서는 로컬 Chrome 실행 파일, `pdfinfo`, `pdffonts`가 필요합니다. `font_files`가 선언된 덱은 선언된 로컬 폰트를 정확히 로드해야 하며, PDF 사전 검증 시 페이지 수, 페이지 크기(16:9, 960×540pt), 이미지 로드, 레이아웃 겹침, 내장 폰트 항목이 검사됩니다.

PowerPoint 수정 파일이 필요한 경우, 선택적 호환성 타깃으로 PPTX를 빌드할 수 있습니다:

```sh
python3 scripts/build_deck.py output/<slug>/deck.json \
  -o output/<slug>/<slug> --targets pptx
```

## 산출물 구조 규격

원문 분석(`source-analysis.md`), 논지 그래프(`argument-map.md`), 주장 원장(`claim-ledger.json`), 슬라이드 아웃라인(`slide-outline.md`), 덱 명세(`deck.json`), 캐릭터 앵커(`character/anchor.png`), 일러스트레이션(`illustrations/`), 폰트(`fonts/`), HTML, PDF 파일은 모두 `output/<slug>/` 경로에 함께 보관됩니다. 렌더러는 검증된 로컬 자산만 조립하며, 원문 탐색이나 이미지 자동 생성을 수행하지 않습니다.

최종 완료 보고 전에는 [`references/review-checklist.md`](references/review-checklist.md)를 통해 모든 관문이 통과되었는지 확인합니다.

## 출처 및 레퍼런스 (Acknowledgements)

- 영감을 받은 레포지토리: [`moongiadventures-dev/handdrawn-ppt`](https://github.com/moongiadventures-dev/handdrawn-ppt)

## 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)에 따라 라이선스가 부여됩니다.

