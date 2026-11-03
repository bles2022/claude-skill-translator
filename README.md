# skill-translator

Claude Code에 설치된 스킬·플러그인 스킬·슬래시 명령어의 **영문 설명을 한국어(또는 원하는 나라의 언어)로 번역**해서,
검색할 수 있는 목록(Markdown + HTML)으로 만들어 주는 Claude Code 플러그인입니다.

*English below.*

---

## 이런 분께 필요합니다

- 스킬을 잔뜩 설치했는데 설명이 전부 영어라서 뭐가 뭔지 모르겠는 분
- 팀원에게 "우리 회사에 깔린 스킬 목록"을 한국어로 공유하고 싶은 분
- 일본어·베트남어 등 다른 언어 사용자와 함께 Claude Code를 쓰는 팀

## 특징

- **API 키가 필요 없습니다** — 번역은 지금 쓰고 있는 Claude가 직접 합니다.
- **`/` 메뉴에도 한국어 표시 (선택)** — 원하면 스킬 설명 앞에 한국어 요약을 붙여 메뉴에서 바로 보이게 합니다.
  영어 원문은 그대로 남겨 Claude의 스킬 선택에는 영향이 없고, 원본은 백업되며 언제든 되돌릴 수 있습니다.
  플러그인 업데이트로 덮어써지면 다음 세션 시작 때 자동으로 다시 붙입니다.
- **바뀐 것만 다시 번역합니다** — 한 번 번역한 스킬은 저장해 두고, 새로 설치됐거나 원문이 바뀐 스킬만 번역합니다.
- **새 스킬 자동 알림** — 세션을 시작할 때 번역 안 된 스킬이 있으면 알려 줍니다.
- **30개국 언어 설정** — 한국, 일본, 중국, 대만, 베트남, 태국, 인도네시아, 독일, 프랑스, 스페인, 브라질 등. 목록에 없으면 언어 코드로 지정.
- 파일이 없는 claude.ai 계정 스킬과 내장 스킬(`/loop`, `/schedule` 등)도 대화 중에 함께 번역합니다.

## 설치

Claude Code에서:

```
/plugin marketplace add bles2022/claude-skill-translator
/plugin install skill-translator@skill-translator
```

설치 후 Claude Code를 다시 시작하세요. Python 3이 필요합니다 (추가 패키지 없음).

<details>
<summary>플러그인 없이 수동 설치</summary>

`plugins/skill-translator/skills/skill-translator` 폴더를 `~/.claude/skills/` 아래로 복사하면 됩니다.
이 경우 새 스킬 알림을 쓰려면 `~/.claude/settings.json`에 SessionStart 훅을 직접 추가해야 합니다:

```json
"hooks": {
  "SessionStart": [
    { "hooks": [ { "type": "command",
      "command": "python3 ~/.claude/skills/skill-translator/scripts/skilltr.py check || python ~/.claude/skills/skill-translator/scripts/skilltr.py check",
      "timeout": 15 } ] }
  ]
}
```
</details>

## 사용법

Claude Code에서 이렇게 말하면 됩니다:

| 하고 싶은 것 | 이렇게 말하기 |
|---|---|
| 설치된 스킬 전체 번역 | `스킬 설명 한글로 정리해줘` |
| 새로 깔린 스킬만 번역 | `스킬 번역 업데이트해줘` |
| 언어 바꾸기 | `국가를 일본으로 설정하고 스킬 번역해줘` |
| 한 번만 다른 언어로 | `스킬 목록 베트남어로 만들어줘` |
| `/` 메뉴에도 한국어로 보이게 | `메뉴에도 한국어로 보이게 해줘` |
| 메뉴를 원래대로 | `스킬 설명 원래대로 되돌려줘` |

> `/` 메뉴 표시는 **파일이 내 컴퓨터에 있는 스킬**(개인·프로젝트·플러그인 스킬)만 바뀝니다.
> claude.ai 계정 스킬(`anthropic-skills:*`)과 내장 명령(`/loop` 등)은 앱이 관리하므로 바뀌지 않습니다 — 이런 스킬은 HTML 목록에서 보세요.

결과물은 `~/.claude/skill-translations/` 폴더에 생깁니다:

- `skills_ko.html` — 브라우저로 여세요. 검색창이 있고, 항목을 누르면 번역문과 원문이 함께 보입니다.
- `skills_ko.md` — 표로 정리된 Markdown

## 동작 방식

1. `skilltr.py scan` — 개인 스킬(`~/.claude/skills`), 프로젝트 스킬(`.claude/skills`), 켜져 있는 플러그인의 skills/commands를 모으고, 번역이 필요한 것만 골라냅니다.
2. Claude가 번역합니다. 도구 이름·파일 확장자·브랜드명은 원문 그대로 두고, "MANDATORY" 같은 강조어는 의미를 살려 옮깁니다.
3. `skilltr.py save` / `build` — 번역을 저장하고 목록을 만듭니다.

## 라이선스

MIT. 번역 결과물은 각 원본 스킬의 라이선스를 따릅니다 — 번역본을 공개 배포할 때는 원본 라이선스를 확인하세요.

---

## English

A Claude Code plugin that translates the descriptions of your installed skills, plugin skills and slash commands
into your language (Korean by default) and builds a searchable Markdown/HTML catalog.

- No API key — the Claude you are already using does the translating.
- Optional: show translations in the `/` menu by prefixing a translated summary to on-disk skill
  descriptions (English kept, originals backed up, `restore` undoes it, re-applied after plugin updates).
  claude.ai account skills and built-in commands are app-managed and stay unchanged.
- Caches translations and only re-translates new or changed skills.
- SessionStart hook tells you when new skills are untranslated.
- Pick a country (`JP`, `VN`, `DE`, `BR`, … 30 built in) or any BCP-47 language code.

**Install**

```
/plugin marketplace add bles2022/claude-skill-translator
/plugin install skill-translator@skill-translator
```

**Use** — ask Claude: *"translate my installed skill descriptions"*, *"set country to Japan and translate my skills"*,
or *"update skill translations"*. Output goes to `~/.claude/skill-translations/skills_<lang>.html`.

Requires Python 3 (standard library only). MIT licensed.
