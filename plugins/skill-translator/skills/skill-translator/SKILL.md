---
name: skill-translator
description: Translate the descriptions of every installed Claude skill, plugin skill and slash command into the user's language (Korean by default; set a country such as JP, VN, DE to switch) and build a searchable catalog. Use when the user asks to translate, localize or explain installed skills in Korean or another language, or to change the target country/language. 설치된 스킬·플러그인 스킬·명령어 설명을 한국어(또는 설정한 국가의 언어)로 번역해 검색 가능한 목록을 만든다. "스킬 설명 한글로", "스킬 번역", "국가 설정 일본" 같은 요청에 사용.
---

# Skill Translator

설치된 스킬 설명을 사용자의 언어로 번역해 **카탈로그(Markdown + HTML)** 로 만든다.
원본 SKILL.md는 절대 수정하지 않는다 — 플러그인 업데이트 때 덮어써지고, 설명은
Claude가 스킬을 언제 쓸지 판단하는 트리거 문구이기 때문이다.

모든 명령은 이 스킬 폴더(스킬을 불러올 때 표시되는 "Base directory for this skill")의
`scripts/skilltr.py`로 실행한다. 아래 `$S`는 그 경로이며, 파이썬은 `python3` → `python` → `py` 순으로 쓴다:

```
S="<이 스킬의 base directory>/scripts/skilltr.py"
```

## 1. 언어 설정 (요청에 국가/언어가 있을 때만)

- 국가로: `python $S config --country JP` (KR, JP, CN, TW, VN, TH, ID, DE, FR, ES, BR … `languages.json` 참고)
- 국가명도 가능: `--country Japan` / `--country 日本`
- 목록에 없는 언어: `python $S config --language sw` (BCP-47 코드)
- 현재 설정 확인: `python $S config`

설정은 `~/.claude/skill-translations/config.json`에 저장되어 다음 실행과 플러그인 업데이트 후에도 유지된다. 한 번만 다른 언어로 뽑고 싶으면
설정을 바꾸지 말고 아래 명령에 `--lang ja`를 붙인다.

## 2. 스캔

```
python $S scan --project "<현재 작업 폴더>"
```

개인 스킬(`~/.claude/skills`, `~/.claude/commands`), 프로젝트 스킬(`.claude/`),
활성화된 플러그인의 skills/commands를 모은다. 이미 번역됐고 원문이 바뀌지 않은 항목은
건너뛰고, 번역이 필요한 항목만 `~/.claude/skill-translations/pending.json`에 쓴다.

## 3. 디스크에 없는 스킬도 포함

claude.ai 계정 스킬(`anthropic-skills:*`)과 내장 스킬(`/loop`, `/schedule`, `/simplify` 등)은
디스크에 파일이 없다. 대신 **지금 대화의 사용 가능한 스킬 목록(system 메시지)에 이름과 설명이
있으니** 그 목록에서 가져와 pending 항목에 추가한다. 이때:

- `id`: `context::<스킬 이름>`, `source`: `context`, `kind`: `skill`
- `hash`: 비워 둠
- 이미 캐시(`~/.claude/skill-translations/<lang>.json`)에 같은 id가 있으면 다시 번역하지 않는다
  (사용자가 "전부 다시"를 요청한 경우 제외)
- 이 스킬(skill-translator) 자신은 제외

## 4. 번역

pending.json을 읽고 각 항목에 두 필드를 채워 `~/.claude/skill-translations/translated.json`에 저장한다.
형식은 pending과 같은 `{"items": [...]}`, 각 항목은 원래 필드(id, name, kind, source, hash,
description)를 그대로 유지한다.

- `summary`: 한 줄 요약 (40자 안팎). "무엇을 해 주는지"를 사용자 관점으로.
- `translation`: description 전체 번역.

번역 규칙:
- 대상 언어는 config의 `language`(또는 `--lang`). 해당 국가에서 실제 쓰는 자연스러운 표현과
  존댓말 수준(한국어는 "~합니다/~할 때 사용" 체)을 쓴다.
- **번역하지 않는 것**: 스킬/명령 이름, 도구 이름(`use_figma`, `get_design_context`),
  파일 확장자(.docx, .pptx), 제품·브랜드명(Figma, Slack, Google Docs), 코드·경로·플래그.
- "MANDATORY", "NEVER" 같은 강조는 의미를 살려 옮긴다 (예: **필수**, **절대 ~하지 말 것**).
- 트리거 예시 문구("implement this design")는 번역하고 원문을 괄호로 남긴다.
- 원문이 이미 대상 언어면 그대로 두고 summary만 만든다.

항목이 많으면(30개 이상) 20개 단위로 나눠 번역하고 매번 save 하면 중간에 끊겨도 이어서 할 수 있다.

## 5. 저장 및 카탈로그 생성

```
python $S save --input ~/.claude/skill-translations/translated.json
python $S build --project "<현재 작업 폴더>"
```

결과:
- `~/.claude/skill-translations/skills_<lang>.md` — 표 형식
- `~/.claude/skill-translations/skills_<lang>.html` — 검색창, 펼치면 번역 + 원문, 다크모드 지원

`build` 결과의 `stale`(원문이 바뀐 항목)이나 `missing`이 0이 아니면 2단계부터 다시 돌린다.

## / 메뉴에 한국어 표시 (선택)

사용자가 "메뉴에도 한국어로 보이게 해줘"처럼 요청하면:

```
python $S apply --project "<현재 작업 폴더>"
```

디스크에 있는 스킬(개인·프로젝트·플러그인)의 description 앞에 번역 요약을 붙인다:
`<한 줄 요약> · <영어 원문>`. 영어 원문은 그대로 남기므로 Claude의 스킬 선택 기준은 바뀌지 않는다.
원본은 `~/.claude/skill-translations/backups/`에 백업되고, 플러그인 업데이트로 덮어써지면
SessionStart 훅이 자동으로 다시 붙인다. 새 세션부터 메뉴에 반영된다.

- 되돌리기: `python $S restore` (모든 파일을 원본으로 되돌리고 자동 적용도 끔)
- claude.ai 계정 스킬(`anthropic-skills:*`)과 내장 스킬은 앱이 관리하는 파일이라 바꿀 수 없다.
  사용자가 직접 만든 계정 스킬이면 claude.ai 스킬 설정에서 설명을 고치라고 안내하고,
  원하면 붙여 넣을 한국어 설명을 만들어 준다.

## 자동 알림 (SessionStart 훅)

SessionStart 훅(플러그인으로 설치하면 자동 등록, 수동 설치면 `~/.claude/settings.json`)이 세션 시작 때 `skilltr.py check`를 실행해,
번역 안 된 새 스킬이나 설명이 바뀐 스킬이 있으면 알림을 띄운다. 디스크의 스킬만 감지하며
(계정 스킬·내장 스킬은 감지 불가) 아무 것도 번역하지 않는다 — 번역은 사용자가 요청할 때 2단계부터 진행.

## 6. 사용자에게 보고

- 번역한 개수 / 재사용한 개수 / 언어
- HTML 파일 경로 (사용자가 열 수 있도록 SendUserFile 등으로 전달 가능하면 전달)
- 대화 안에서 바로 보고 싶어 하면 출처별로 `이름 — 한 줄 요약` 목록만 보여 준다
  (전체 번역은 파일에 있음)
