"""skill-translator helper.

Subcommands
  config  [--country KR | --language ko]   show or change the target language
  scan    [--lang ko] [--project DIR]      list installed skills; write pending.json (new/changed only)
  save    --input FILE [--lang ko]         merge translated items into the translation cache
  build   [--lang ko] [--project DIR]      write the translated catalog (Markdown + HTML)
  check   [--lang ko] [--project DIR]      SessionStart hook: notice if anything is untranslated

The script never modifies any installed SKILL.md. Translations live in
~/.claude/skill-translations/<lang>.json and are reused until the source text changes.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = SKILL_DIR / "config.json"
LANG_MAP_PATH = SKILL_DIR / "languages.json"
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
OUT_DIR = CLAUDE_HOME / "skill-translations"
# User settings live outside the skill folder so plugin updates don't reset them.
CONFIG_PATH = OUT_DIR / "config.json"


# ---------- config ----------

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_language(country=None, language=None):
    langs = load_json(LANG_MAP_PATH, {})
    if language:
        for code, info in langs.get("countries", {}).items():
            if info["language"].lower() == language.lower():
                return code, info
        return None, {"language": language, "name": language, "native": language}
    code = country.upper()
    info = langs.get("countries", {}).get(code)
    if not info:
        for c, i in langs.get("countries", {}).items():
            if code.lower() in (i.get("country", "").lower(), i.get("country_native", "").lower()):
                return c, i
        sys.exit(f"Unknown country '{country}'. Use --language <BCP-47 code> instead, or add it to languages.json.")
    return code, info


def load_config():
    return load_json(CONFIG_PATH, None) or load_json(DEFAULT_CONFIG_PATH, {"country": "KR", "language": "ko"})


def current_lang(args_lang=None):
    if args_lang:
        return args_lang
    return load_config().get("language", "ko")


def cmd_config(args):
    cfg = load_config()
    if args.country or args.language:
        code, info = resolve_language(args.country, args.language)
        cfg = {
            "country": code,
            "language": info["language"],
            "language_name": info.get("name", info["language"]),
            "language_native": info.get("native", ""),
        }
        save_json(CONFIG_PATH, cfg)
        print("updated")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))


# ---------- frontmatter ----------

def parse_frontmatter(text):
    m = re.match(r"^\ufeff?---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", text, re.S)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end():]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(block)
        if isinstance(data, dict):
            return data, body
    except Exception:
        pass
    return _mini_yaml(block), body


def _mini_yaml(block):
    """Top-level `key: value` pairs only: plain, quoted, folded (>) and literal (|) scalars."""
    data, lines, i = {}, block.splitlines(), 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val[:1] in (">", "|"):
            folded, parts = val[0] == ">", []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
                parts.append(lines[i].strip())
                i += 1
            val = (" " if folded else "\n").join(p for p in parts).strip()
        elif val[:1] in ('"', "'"):
            q = val[0]
            while not (len(val) > 1 and val.endswith(q) and not val.endswith("\\" + q)) and i < len(lines):
                val += " " + lines[i].strip()
                i += 1
            val = val[1:-1]
            val = val.replace('\\"', '"').replace("\\\\", "\\") if q == '"' else val.replace("''", "'")
        else:
            while i < len(lines) and lines[i][:1] in (" ", "\t") and lines[i].strip():
                val += " " + lines[i].strip()
                i += 1
        data[key] = val
    return data


def first_body_line(body):
    for line in body.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:300]
    return ""


# ---------- discovery ----------

def enabled_plugins():
    settings = load_json(CLAUDE_HOME / "settings.json", {})
    enabled = settings.get("enabledPlugins", {})
    installed = load_json(CLAUDE_HOME / "plugins" / "installed_plugins.json", {}).get("plugins", {})
    for key, entries in installed.items():
        if enabled.get(key) is False or not entries:
            continue
        entry = sorted(entries, key=lambda e: e.get("lastUpdated", ""))[-1]
        path = Path(entry["installPath"])
        if path.exists():
            yield key.split("@")[0], path


def collect_from(root, source, prefix=""):
    items = []
    skills = Path(root) / "skills"
    if skills.is_dir():
        for md in sorted(skills.glob("*/SKILL.md")):
            fm, body = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            name = str(fm.get("name") or md.parent.name)
            items.append(make_item(prefix + name, "skill", source, md, fm, body))
    commands = Path(root) / "commands"
    if commands.is_dir():
        for md in sorted(commands.rglob("*.md")):
            fm, body = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            name = ":".join(md.relative_to(commands).with_suffix("").parts)
            items.append(make_item(prefix + name, "command", source, md, fm, body))
    return items


def make_item(name, kind, source, path, fm, body):
    desc = str(fm.get("description") or "").strip() or first_body_line(body)
    when = str(fm.get("when_to_use") or fm.get("when-to-use") or "").strip()
    text = desc + ("\n\nWhen to use: " + when if when else "")
    return {
        "id": f"{source}::{name}",
        "name": name,
        "kind": kind,
        "source": source,
        "path": str(path),
        "description": text,
        "hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
    }


def discover(project_dir=None):
    items = collect_from(CLAUDE_HOME, "personal")
    if project_dir:
        items += collect_from(Path(project_dir) / ".claude", "project")
    for plugin, path in enabled_plugins():
        items += collect_from(path, f"plugin:{plugin}", prefix=f"{plugin}:")
    return [it for it in items if not it["name"].endswith("skill-translator")]


# ---------- commands ----------

def cache_path(lang):
    return OUT_DIR / f"{lang}.json"


def cmd_scan(args):
    lang = current_lang(args.lang)
    cache = load_json(cache_path(lang), {})
    items = discover(args.project)
    pending = [it for it in items if cache.get(it["id"], {}).get("hash") != it["hash"]]
    save_json(OUT_DIR / "pending.json", {"language": lang, "items": pending})
    print(json.dumps({
        "language": lang,
        "total_on_disk": len(items),
        "already_translated": len(items) - len(pending),
        "pending": len(pending),
        "pending_file": str(OUT_DIR / "pending.json"),
        "cache_file": str(cache_path(lang)),
    }, ensure_ascii=False, indent=2))


def cmd_check(args):
    """SessionStart hook: print a notice only when installed skills lack a translation."""
    project = args.project
    if not project and not sys.stdin.isatty():
        try:
            project = json.loads(sys.stdin.read() or "{}").get("cwd")
        except (json.JSONDecodeError, ValueError):
            pass
    lang = current_lang(args.lang)
    cache = load_json(cache_path(lang), {})
    items = discover(project)
    new = [it["name"] for it in items if it["id"] not in cache]
    changed = [it["name"] for it in items if it["id"] in cache and cache[it["id"]].get("hash") != it["hash"]]
    if not new and not changed:
        return
    names = ", ".join((new + changed)[:5]) + (" …" if len(new) + len(changed) > 5 else "")
    if lang.startswith("ko"):
        parts = ([f"새 스킬 {len(new)}개"] if new else []) + ([f"설명이 바뀐 스킬 {len(changed)}개"] if changed else [])
        msg = f"[skill-translator] 번역 안 된 {' / '.join(parts)}: {names} — \"스킬 번역 업데이트해줘\"라고 하면 번역합니다."
    else:
        parts = ([f"{len(new)} new"] if new else []) + ([f"{len(changed)} changed"] if changed else [])
        msg = f"[skill-translator] Untranslated skills ({lang}): {', '.join(parts)} — {names}. Ask \"update skill translations\" to translate."
    print(json.dumps({
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg + " (handle with the skill-translator skill if the user asks)",
        },
    }, ensure_ascii=False))


def cmd_save(args):
    lang = current_lang(args.lang)
    data = load_json(args.input, None)
    if data is None:
        sys.exit(f"Cannot read {args.input}")
    rows = data.get("items", data) if isinstance(data, dict) else data
    cache = load_json(cache_path(lang), {})
    saved = 0
    for row in rows:
        if not row.get("id") or not row.get("translation"):
            continue
        cache[row["id"]] = {
            "name": row.get("name", row["id"].split("::")[-1]),
            "kind": row.get("kind", "skill"),
            "source": row.get("source", row["id"].split("::")[0]),
            "hash": row.get("hash", ""),
            "summary": row.get("summary", ""),
            "translation": row["translation"],
            "original": row.get("description", ""),
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        saved += 1
    save_json(cache_path(lang), cache)
    print(f"saved {saved} translations -> {cache_path(lang)}")


def cmd_build(args):
    lang = current_lang(args.lang)
    cfg = load_config()
    cache = load_json(cache_path(lang), {})
    on_disk = {it["id"]: it for it in discover(args.project)}
    rows = []
    for key, entry in cache.items():
        live = on_disk.get(key)
        if key.split("::")[0] != "context" and not live:
            continue  # uninstalled since it was translated
        rows.append({**entry, "id": key, "stale": bool(live and live["hash"] != entry.get("hash"))})
    rows.sort(key=lambda r: (source_rank(r["source"]), r["source"], r["name"]))
    missing = [k for k in on_disk if k not in cache]

    title = f"Skill catalog ({lang})"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# {title}", "", f"_generated {stamp} · {len(rows)} items_", ""]
    for src, group in group_by(rows):
        md += [f"## {src}", "", "| name | summary | description |", "|---|---|---|"]
        for r in group:
            flag = " ⚠" if r["stale"] else ""
            md.append(f"| `{r['name']}`{flag} | {cell(r.get('summary'))} | {cell(r['translation'])} |")
        md.append("")
    if missing:
        md += ["## not translated yet", ""] + [f"- `{k}`" for k in missing] + [""]
    md_path = OUT_DIR / f"skills_{lang}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    html_path = OUT_DIR / f"skills_{lang}.html"
    html_path.write_text(render_html(rows, missing, lang, cfg, stamp), encoding="utf-8")
    print(json.dumps({"markdown": str(md_path), "html": str(html_path),
                      "items": len(rows), "stale": sum(r["stale"] for r in rows),
                      "missing": len(missing)}, ensure_ascii=False, indent=2))


def source_rank(src):
    return {"personal": 0, "project": 1}.get(src, 3 if src.startswith("context") else 2)


def group_by(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["source"], []).append(r)
    return groups.items()


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_html(rows, missing, lang, cfg, stamp):
    esc = html.escape
    cards = []
    for src, group in group_by(rows):
        cards.append(f'<h2>{esc(src)} <span class="n">{len(group)}</span></h2>')
        for r in group:
            stale = '<span class="stale">원문 변경됨</span>' if r["stale"] else ""
            summary = f'<p class="sum">{esc(r.get("summary") or "")}</p>' if r.get("summary") else ""
            cards.append(
                f'<details class="card" data-q="{esc((r["name"] + " " + r["translation"] + " " + r.get("summary", "")).lower())}">'
                f'<summary><code>{esc(r["name"])}</code> <span class="kind">{esc(r["kind"])}</span>{stale}{summary}</summary>'
                f'<p class="tr">{esc(r["translation"])}</p>'
                f'<p class="orig">{esc(r.get("original") or "")}</p></details>')
    miss = ""
    if missing:
        miss = "<h2>미번역</h2><ul>" + "".join(f"<li><code>{esc(m)}</code></li>" for m in missing) + "</ul>"
    return f"""<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Skill catalog · {esc(lang)}</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--line:#e4e2dc;--card:#fff;--acc:#c2410c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161614;--fg:#ecebe6;--mut:#9b9a93;--line:#2e2d2a;--card:#1f1f1c;--acc:#fb923c}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
main{{max-width:880px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:22px;margin:0 0 4px}} .meta{{color:var(--mut);font-size:13px;margin-bottom:16px}}
input{{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}}
h2{{font-size:15px;margin:28px 0 8px;color:var(--mut)}} .n{{font-weight:400}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:6px 0}}
summary{{cursor:pointer;list-style:none}} summary::-webkit-details-marker{{display:none}}
code{{font-weight:600}} .kind{{font-size:12px;color:var(--mut);margin-left:6px}}
.stale{{font-size:12px;color:var(--acc);margin-left:6px}}
.sum{{margin:4px 0 0;color:var(--mut)}} .tr{{margin:10px 0 6px}}
.orig{{margin:0;font-size:13px;color:var(--mut);border-top:1px dashed var(--line);padding-top:6px}}
</style></head><body><main>
<h1>Skill catalog — {esc(cfg.get("language_native") or cfg.get("language_name") or lang)}</h1>
<div class="meta">{esc(stamp)} · {len(rows)} items · 클릭하면 전체 번역과 원문을 볼 수 있습니다</div>
<input id="q" placeholder="검색 / search…" autocomplete="off">
{''.join(cards)}{miss}
</main><script>
document.getElementById('q').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();
document.querySelectorAll('.card').forEach(c=>c.style.display=c.dataset.q.includes(q)?'':'none')}});
</script></body></html>"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("config")
    c.add_argument("--country")
    c.add_argument("--language")
    s = sub.add_parser("scan")
    s.add_argument("--lang")
    s.add_argument("--project")
    v = sub.add_parser("save")
    v.add_argument("--input", required=True)
    v.add_argument("--lang")
    b = sub.add_parser("build")
    b.add_argument("--lang")
    b.add_argument("--project")
    k = sub.add_parser("check")
    k.add_argument("--lang")
    k.add_argument("--project")
    args = p.parse_args()
    {"config": cmd_config, "scan": cmd_scan, "save": cmd_save, "build": cmd_build,
     "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
