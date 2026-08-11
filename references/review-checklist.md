# Review checklist

이 문서는 `SKILL.md`와 분야별 레퍼런스를 하나의 최종 검수 흐름으로 묶는
판정표다. 세부 판단은 각 링크의 원문을 따르고, 이 문서는 각 관문을 통과했는지
확인하는 데 사용한다.

## 사용 방법

각 항목에 `PASS`, `REVIEW`, `BLOCKED`, `N/A` 중 하나를 기록한다.

- `PASS`: 근거가 확인되었고 다음 관문으로 진행할 수 있음
- `REVIEW`: 작업은 진행할 수 있으나 발표·배포 전에 담당자 확인이 필요함
- `BLOCKED`: 산출물을 완료로 판정할 수 없음
- `N/A`: 해당 프로젝트에 적용되지 않음. 이유를 기록함

`REVIEW` 또는 `BLOCKED` 항목에는 파일 경로, 슬라이드 번호, source line,
또는 preflight 결과를 함께 적는다.

## 0. 프로젝트 입력과 승인 범위

- [ ] source 파일을 원문 그대로 보존했는가? → [SKILL.md](../SKILL.md#1-read-and-segment-the-source)
- [ ] 언어, 청중, 발표 시간/페이지 수, 화면비, line mode, visual mode가 정해졌는가?
- [ ] character anchor와 사용 가능한 로컬 자산이 확인되었는가? → [character-continuity.md](character-continuity.md)
- [ ] 이전 실행 결과를 덮어쓰지 않고 별도 `output/<slug>/`에 저장했는가?
- [ ] 생성할 이미지 수와 최종 출력 대상(HTML, PDF, 선택적 PPTX)이 승인되었는가?

## 1. 편집·논지 검수

- [ ] source profile에 제목, 장르, 청중 단서, 논제, 중심 질문, 주요 절과 미해결 사항이 있는가?
- [ ] argument map이 주장 → 이유 → 근거/인용 → 해석 → 적용을 연결하는가?
- [ ] 슬라이드마다 한 문장 takeaway가 있고, 각 슬라이드가 전체 논지에 필요한가?
- [ ] 원문의 긴 반복은 speaker notes로 옮기고 화면 텍스트는 과밀하지 않은가?
- [ ] 반론, 긴장, 전환, 결론이 요약 과정에서 사라지지 않았는가? → [editorial-analysis.md](editorial-analysis.md)

## 2. 출처·주장·불확실성 검수

- [ ] 각 외부 사실, 날짜, 인명, 숫자, 번역·어원 주장이 검증되었거나 `NEEDS-REVIEW`로 표시되었는가?
- [ ] 직접 인용, 원문 주장, 외부 사실, 해석, 추론, 적용이 서로 구분되는가?
- [ ] 화면의 source footer와 speaker notes의 출처가 실제 source line/reference와 일치하는가?
- [ ] 슬라이드 하단 source footer에 '검토 필요', 'NEEDS-REVIEW' 등 내부 검수 메모가 누출되지 않고 정제된 출처 표기만 노출되는가? → [source-and-citation.md](source-and-citation.md)
- [ ] 성서·기타 1차 텍스트의 본문, 번역, 발표자의 해석이 섞여 단정적으로 보이지 않는가?
- [ ] 민감한 종교·역사·집단 비교가 희화화나 무근거 일반화가 되지 않았는가? → [source-and-citation.md](source-and-citation.md)

## 3. 아웃라인·스키마 검수

- [ ] 모든 슬라이드에 고유한 `id`, headline, takeaway, role이 있는가?
- [ ] 각 슬라이드에 source line/reference가 있거나 cover/transition 예외가 명시되어 있는가?
- [ ] visible text, speaker notes, visual scene, character action, transition, risk가 논지와 맞는가?
- [ ] body와 visible_text가 동일하여 동일한 텍스트가 화면에 중복 렌더링되지 않는가? → [outline-schema.md](outline-schema.md)
- [ ] layout, theme, aspect ratio가 지원 범위 안에 있는가?
- [ ] 자동 검증을 통과했는가?

```sh
python3 scripts/validate_outline.py output/<slug>/deck.json
```

세부 필드 계약은 [outline-schema.md](outline-schema.md)를 따른다. 아웃라인 승인
전에는 유료 이미지 일괄 생성을 진행하지 않는다.

## 4. 시각·캐릭터 검수

- [ ] 모든 장면에서 anchor의 얼굴, 머리, 의상, 비율, 팔레트, 역할이 유지되는가?
- [ ] 캐릭터가 예수, 바울, 실존 인물 또는 보호 대상 인물을 불필요하게 impersonate하지 않는가?
- [ ] 이미지가 장식이 아니라 주장·관계·시간·전환을 설명하는가?
- [ ] 일러스트레이션이 하얀 박스가 아닌 투명 배경(Transparent PNG) 또는 `mix-blend-mode`를 통해 슬라이드에 자연스럽게 통합되었는가? → [character-continuity.md](character-continuity.md)
- [ ] 지도·timeline·comparison·flow·table이 실제 구조를 명확하게 하는 경우에만 사용되었는가?
- [ ] 모든 페이지를 나란히 놓고 캐릭터 drift, 여백, 시각적 반복을 검토했는가? → [character-continuity.md](character-continuity.md)

## 5. HTML·PDF 기술 검수

- [ ] HTML이 reviewed `deck.json`과 로컬 자산만으로 생성되는가?
- [ ] 브라우저에서 페이지 이동, hash 링크, Notes 패널, 인쇄 동작이 되는가?
- [ ] `window.__DECK_READY__`가 true가 되고 모든 이미지가 로드되는가?
- [ ] PDF 페이지 수가 덱과 같고, 페이지 크기가 960×540pt(16:9)인가?
- [ ] 잘린 콘텐츠, overflow, 빈 페이지, 깨진 이미지가 없는가?
- [ ] 메인 타이틀(`h1`)과 서브 문장(`takeaway`) 및 본문이 플렉스 컬럼 컨테이너로 감싸여 텍스트 상호 간 겹침(Text-to-text overlap)이 방지되었는가?
- [ ] `full` 페이지의 캡션이 이미지 아래의 예약된 캡션 레일에 있고 이미지와 교차하지 않는가?
- [ ] `content`/`comparison`/`timeline`/`flow`/`table`의 본문·토큰이 오른쪽 이미지 레일과 교차하지 않는가?
- [ ] 브라우저 레이아웃 preflight의 `layoutIssues`(텍스트-삽화 및 텍스트-텍스트 겹침)가 빈 배열인가?
- [ ] `font_files`가 선언된 경우 해당 폰트만 PDF에 embedding되며 fallback이 없는가?
- [ ] 대표 페이지와 마지막 페이지를 실제 렌더링 이미지로 확인했는가?

```sh
python3 scripts/build_deck.py output/<slug>/deck.json \
  -o output/<slug>/<slug>-html --targets html,pdf
```

렌더링 규칙과 PDF preflight 세부 사항은 [rendering.md](rendering.md)를 따른다.
렌더러가 없는 경우에는 PDF가 생성되었다고 주장하지 말고, 검증된 `deck.json`과
자산/프롬프트 manifest만 남긴다.

## 6. 최종 산출물·저장소 검수

- [ ] `source-analysis.md`, `argument-map.md`, `claim-ledger.json`, `slide-outline.md`, `deck.json`이 존재하는가?
- [ ] `character/anchor.*`, `illustrations/`, 선언된 `fonts/`, HTML, PDF가 output 경로에 있는가?
- [ ] 출력 파일이 source를 덮어쓰지 않았고, 임시 파일·캐시·로컬 의존성이 커밋 대상에서 제외되었는가?
- [ ] 테스트와 Python 구문 검사가 통과했는가?

```sh
npm test
python3 -m compileall -q scripts tests
git diff --check
git status --short
```

- [ ] 남은 `REVIEW`/`BLOCKED` 항목이 없거나, 담당자·기한·판정 근거가 기록되었는가?
- [ ] 최종 커밋에 검수 문서와 산출물이 함께 포함되었는가?

## 최종 판정

| 관문 | 판정 | 근거/메모 |
| --- | --- | --- |
| 입력·승인 범위 |  |  |
| 편집·논지 |  |  |
| 출처·불확실성 |  |  |
| 아웃라인·스키마 |  |  |
| 시각·캐릭터 |  |  |
| HTML·PDF |  |  |
| 산출물·저장소 |  |  |

최종 상태: `PASS` / `REVIEW` / `BLOCKED`
