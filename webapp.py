"""Lokale Verwaltungsoberfläche für Empfänger, Zeitplan, Themen und Quellen."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from plistlib import dump

import yaml
from flask import Flask, flash, redirect, render_template_string, request, url_for

from config.loader import load_env_settings, load_profiles as load_profiles_config, load_special_topics, load_topics
from config.models import SourceConfig, TopicConfig

ROOT = Path(__file__).resolve().parent
TOPICS_FILE = ROOT / "config" / "topics.yaml"
PLIST_FILE = Path.home() / "Library" / "LaunchAgents" / "com.hannes.juramonitor.plist"
LABEL = "com.hannes.juramonitor"
PROFILES_FILE = ROOT / "config" / "profiles.yaml"
ENV_FILE = ROOT / ".env"
PYTHON = ROOT / ".venv" / "bin" / "python"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROFILE_PAGE = ""

app = Flask(__name__)
app.secret_key = os.environ.get("JURA_MONITOR_UI_SECRET", "local-jura-monitor")

PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jura-Monitor Verwaltung</title>
<style>
:root{--ink:#17212b;--muted:#64717d;--line:#dbe2e7;--paper:#f5f7f8;--white:#fff;--accent:#0b6e69;--accent-dark:#07514e;--warm:#c96b32;--danger:#a33b36}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#173c3b;color:#fff;padding:36px max(24px,calc((100% - 1120px)/2));display:flex;justify-content:space-between;gap:20px;align-items:end}header h1{margin:0;font:700 34px/1.05 Georgia,serif;letter-spacing:0}header p{margin:8px 0 0;color:#c5d7d3}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#a7d2c9;font-weight:700}.status{border:1px solid #80b3a8;padding:9px 13px;border-radius:4px;font-size:13px;white-space:nowrap}.wrap{max-width:1120px;margin:28px auto;padding:0 24px}.grid{display:grid;grid-template-columns:330px 1fr;gap:20px;align-items:start}.panel{background:var(--white);border:1px solid var(--line);border-radius:6px;padding:22px;box-shadow:0 4px 18px #173c3b0b}.panel h2{font:700 22px Georgia,serif;margin:0 0 4px}.panel h3{font-size:16px;margin:22px 0 8px}.hint{color:var(--muted);font-size:13px;margin:0 0 18px}.field{margin:14px 0}.field label{display:block;font-size:12px;font-weight:700;color:#3f4e59;margin-bottom:5px}.field input,.field select,.field textarea{width:100%;border:1px solid #bfcbd2;border-radius:4px;padding:10px 11px;font:inherit;background:#fff;color:var(--ink)}.field textarea{min-height:78px;resize:vertical}.inline{display:grid;grid-template-columns:1fr 1fr;gap:10px}.button{display:inline-block;border:0;border-radius:4px;padding:10px 14px;background:var(--accent);color:#fff;font-weight:700;cursor:pointer;font:inherit}.button:hover{background:var(--accent-dark)}.button.secondary{background:#e6eeec;color:var(--accent-dark)}.button.danger{background:#fff0ee;color:var(--danger);border:1px solid #e4b5af}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.notice{padding:11px 14px;border-left:4px solid var(--warm);background:#fff5ec;margin-bottom:18px}.topic{border-top:1px solid var(--line);padding:18px 0}.topic:first-of-type{border-top:0;padding-top:0}.topic-head{display:flex;justify-content:space-between;gap:12px;align-items:start}.topic h3{font:700 20px Georgia,serif;margin:0}.tag{display:inline-block;padding:3px 8px;border-radius:3px;background:#e7f1ef;color:var(--accent-dark);font-size:11px;font-weight:700}.tag.off{background:#edf0f2;color:#71808b}.source{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #edf0f2}.source input[type=checkbox],.topic-head input[type=checkbox]{accent-color:var(--accent);width:16px;height:16px}.source-main{flex:1;min-width:0}.source-name{font-weight:700}.source-url{color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.source-controls{display:flex;gap:5px}.iconbtn{border:1px solid var(--line);background:#fff;border-radius:3px;padding:5px 8px;cursor:pointer;color:var(--muted)}.empty{color:var(--muted);font-style:italic;padding:8px 0}.flash{padding:11px 14px;background:#e7f4ee;border-left:4px solid var(--accent);margin-bottom:18px}.small{font-size:12px;color:var(--muted)}@media(max-width:780px){header{display:block;padding:28px 20px}.status{display:inline-block;margin-top:18px}.wrap{padding:0 14px;margin-top:18px}.grid{grid-template-columns:1fr}.panel{padding:17px}}
</style><style>.toolbar{display:flex;gap:10px;margin:16px 0;align-items:center}.search{flex:1;border:1px solid #bfcbd2;border-radius:4px;padding:10px 11px;font:inherit}.toggle{border:1px solid #dbe2e7;background:#f5f8f7;color:#07514e;border-radius:4px;padding:9px 11px;cursor:pointer;font:inherit}.topic.hidden{display:none}.topic .source{display:none}.topic.expanded .source{display:flex}</style></head><body>
<header><div><div class="eyebrow">Lokale Steuerzentrale</div><h1>Jura-Monitor</h1><p>Versand, Themen und Quellen an einem Ort.</p></div><div class="status">Profile · Themen · Quellen</div></header>
<main class="wrap">{% with messages=get_flashed_messages() %}{% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endwith %}
<div class="grid"><section class="panel"><h2>Versandprofile</h2><p class="hint">Jeder Empfänger wird unabhängig konfiguriert. Rhythmus, Uhrzeit und Themen werden pro Profil festgelegt.</p><div class="actions"><a class="button" href="{{ url_for('profiles') }}">Profile verwalten</a><a class="button secondary" href="{{ url_for('run_now') }}">Testlauf starten</a><a class="button secondary" href="{{ url_for('show_logs') }}">Letzte Logs</a></div>
</section><section class="panel"><h2>Themen</h2><p class="hint">Aktive Themen werden in den ausgewählten Profilen berücksichtigt. Quellen werden separat verwaltet.</p><div class="toolbar"><input id="topic-search" class="search" type="search" placeholder="Thema suchen ..." oninput="filterTopics(this.value)"><a class="toggle" href="{{ url_for('sources') }}">Quellen verwalten</a></div>
{% for topic in topics %}<article class="topic" data-search="{{ topic.name }} {{ topic.id }}"><div class="topic-head"><div><form method="post" action="{{ url_for('toggle_topic', topic_id=topic.id) }}" style="display:inline"><input aria-label="{{ topic.name }} aktivieren" type="checkbox" {% if topic.enabled %}checked{% endif %} onchange="this.form.submit()"></form> <h3 style="display:inline">{{ topic.name }}</h3></div><span class="tag {% if not topic.enabled %}off{% endif %}">{{ 'AKTIV' if topic.enabled else 'PAUSIERT' }}</span></div><div class="small">{{ topic.keywords|length }} Keywords · {{ topic.sources|selectattr('enabled')|list|length }}/{{ topic.sources|length }} Quellen aktiv</div></article>{% endfor %}
<div class="actions"><a class="button" href="{{ url_for('edit_topic', topic_id='new') }}">+ Neues Thema</a><a class="button secondary" href="{{ url_for('sources') }}">Quellen bearbeiten</a></div></section></div></main><script>function filterTopics(value){const term=value.toLowerCase().trim();document.querySelectorAll('.topic').forEach(topic=>topic.classList.toggle('hidden',term&&!topic.dataset.search.toLowerCase().includes(term)))}</script></body></html>"""

FORM = """<!doctype html><html lang=de><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{{ title }}</title><style>body{margin:0;background:#f5f7f8;color:#17212b;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.box{max-width:700px;margin:40px auto;background:#fff;border:1px solid #dbe2e7;border-radius:6px;padding:28px}h1{font:700 28px Georgia,serif;margin-top:0}.field{margin:16px 0}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:5px}.field input,.field select,.field textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #bfcbd2;border-radius:4px;font:inherit}.field textarea{min-height:100px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.buttons{display:flex;gap:8px;margin-top:22px}.button{padding:10px 14px;border:0;border-radius:4px;background:#0b6e69;color:white;font:inherit;font-weight:700;text-decoration:none;cursor:pointer}.secondary{background:#e6eeec;color:#07514e}@media(max-width:740px){.box{margin:15px;padding:20px}.row{grid-template-columns:1fr}}</style></head><body><main class=box><h1>{{ title }}</h1><form method=post>{% for field in fields %}<div class=field><label for={{ field.name }}>{{ field.label }}</label>{% if field.kind=='select' %}<select id={{ field.name }} name={{ field.name }}>{% for value,label in field.options %}<option value={{ value }} {% if field.value==value %}selected{% endif %}>{{ label }}</option>{% endfor %}</select>{% elif field.kind=='textarea' %}<textarea id={{ field.name }} name={{ field.name }}>{{ field.value }}</textarea>{% else %}<input id={{ field.name }} name={{ field.name }} value="{{ field.value }}" {% if field.required %}required{% endif %}>{% endif %}</div>{% endfor %}<div class=buttons><button class=button type=submit>Speichern</button><a class="button secondary" href="{{ url_for('index') }}">Abbrechen</a></div></form></main></body></html>"""


def save_topics(topics: list[TopicConfig]) -> None:
    TOPICS_FILE.write_text(yaml.safe_dump({"topics": [topic.model_dump(exclude_none=True) for topic in topics]}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_profiles() -> list[dict]:
    return [profile.model_dump() for profile in load_profiles_config()]


def save_profiles(profiles: list[dict]) -> None:
    PROFILES_FILE.write_text(yaml.safe_dump({"profiles": profiles}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def schedule_all_profiles() -> None:
    legacy = PLIST_FILE
    subprocess.run(["launchctl", "unload", str(legacy)], capture_output=True, check=False)
    for old_plist in PLIST_FILE.parent.glob(f"{LABEL}.*.plist"):
        subprocess.run(["launchctl", "unload", str(old_plist)], capture_output=True, check=False)
        old_plist.unlink(missing_ok=True)
    scheduled = set()
    for profile in load_profiles():
        send_time = profile.get("send_time", "07:00")
        hour, minute = (int(value) for value in send_time.split(":", 1))
        frequencies = set(profile.get("topic_frequencies", {}).values()) | set(profile.get("special_topic_frequencies", {}).values()) or {"daily"}
        for frequency in frequencies:
            profile_config = next(item for item in load_profiles_config() if item.id == profile["id"])
            signature = (frequency, profile_config.content_signature())
            if signature in scheduled:
                continue
            scheduled.add(signature)
            profile_label = f"{LABEL}.{profile['id']}.{frequency}"
            plist = PLIST_FILE.parent / f"{profile_label}.plist"
            payload = {"Label": profile_label, "ProgramArguments": [str(PYTHON), "main.py", "--scheduled", "--profile", profile["id"], "--frequency", frequency], "WorkingDirectory": str(ROOT), "StartCalendarInterval": {"Hour": hour, "Minute": minute}, "StandardOutPath": str(ROOT / "logs" / "launchd.log"), "StandardErrorPath": str(ROOT / "logs" / "launchd.err.log"), "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 300}
            if frequency == "weekly":
                payload["StartCalendarInterval"]["Weekday"] = 2
            elif frequency == "monthly":
                payload["StartCalendarInterval"]["Day"] = 1
            with plist.open("wb") as file:
                dump(payload, file)
            subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, check=False)
            subprocess.run(["launchctl", "load", "-w", str(plist)], capture_output=True, check=False)


@app.get("/")
def index():
    return render_template_string(PAGE, topics=load_topics(), frequency_label="Profilabhängig", send_time="")


SOURCES_PAGE = """<!doctype html><html lang=de><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Quellenverwaltung</title><style>body{margin:0;background:#f5f7f8;color:#17212b;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.box{max-width:1000px;margin:30px auto;padding:0 18px}.topic{background:#fff;border:1px solid #dbe2e7;border-radius:6px;margin:14px 0;padding:18px}.topic h2{font:700 22px Georgia,serif;margin:0}.search{width:100%;box-sizing:border-box;padding:11px;border:1px solid #bfcbd2;border-radius:4px;font:inherit;margin:10px 0 18px}.source{display:flex;gap:10px;align-items:center;border-top:1px solid #edf0f2;padding:11px 0}.source-main{flex:1;min-width:0}.source-name{font-weight:700}.url{color:#64717d;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tag{font-size:11px;background:#e7f1ef;color:#07514e;padding:3px 7px;border-radius:3px}.tag.off{background:#edf0f2;color:#71808b}.actions{display:flex;gap:7px;flex-wrap:wrap}.button{border:0;border-radius:4px;padding:8px 11px;background:#0b6e69;color:#fff;text-decoration:none;font:inherit;font-weight:700;cursor:pointer}.secondary{background:#e6eeec;color:#07514e}.hidden{display:none}</style></head><body><main class=box><h1>Quellenverwaltung</h1><p>Hier verwaltest du die RSS-Feeds und Webseiten. Änderungen wirken auf alle Empfängerprofile, die das jeweilige Thema ausgewählt haben.</p><input class=search type=search placeholder="Quelle oder Thema suchen ..." oninput="filterSources(this.value)"><div class=actions><a class="button secondary" href="{{ url_for('index') }}">Zur Übersicht</a></div>{% for topic in topics %}<section class=topic data-search="{{ topic.name }} {{ topic.id }} {% for source in topic.sources %}{{ source.name }} {{ source.url }} {% endfor %}"><h2>{{ topic.name }} <span class="tag">{{ topic.sources|length }} Quellen</span></h2>{% for source in topic.sources %}<div class=source><form method=post action="{{ url_for('toggle_source', topic_id=topic.id, source_index=loop.index0) }}"><input aria-label="{{ source.name }} aktivieren" type=checkbox {% if source.enabled %}checked{% endif %} onchange="this.form.submit()"></form><div class=source-main><div class=source-name>{{ source.name }} <span class="tag {% if not source.enabled %}off{% endif %}">{{ 'aktiv' if source.enabled else 'pausiert' }}</span></div><div class=url>{{ source.url }}</div></div><div class=actions><a class="button secondary" href="{{ url_for('edit_source', topic_id=topic.id, source_index=loop.index0) }}">Bearbeiten</a><form method=post action="{{ url_for('delete_source', topic_id=topic.id, source_index=loop.index0) }}"><button class="button secondary" type=submit>Löschen</button></form></div></div>{% else %}<p>Keine Quellen hinterlegt.</p>{% endfor %}<div class=actions><a class=button href="{{ url_for('edit_source', topic_id=topic.id, source_index='new') }}">+ Quelle hinzufügen</a></div></section>{% endfor %}</main><script>function filterSources(value){const term=value.toLowerCase().trim();document.querySelectorAll('.topic').forEach(topic=>topic.classList.toggle('hidden',term&&!topic.dataset.search.toLowerCase().includes(term)))}</script></body></html>"""


@app.get("/sources")
def sources():
    return render_template_string(SOURCES_PAGE, topics=load_topics())


@app.route("/profiles", methods=["GET", "POST"])
def profiles():
    current = load_profiles()
    topics = load_topics()
    if request.method == "POST":
        channels = request.form.getlist("channels") or ["email"]
        recipients = [address.strip() for address in request.form.get("recipients", "").split(",") if address.strip()]
        whatsapp_recipients = [target.strip() for target in request.form.get("whatsapp_recipients", "").split(",") if target.strip()]
        linkedin_organization_ids = [organization_id.strip() for organization_id in request.form.get("linkedin_organization_ids", "").split(",") if organization_id.strip()]

        if "email" in channels and (not recipients or any(not EMAIL_RE.match(address) for address in recipients)):
            flash("Bitte gültige E-Mail-Empfänger im Profil eintragen.")
            return redirect(url_for("profiles"))
        if "whatsapp" in channels and not whatsapp_recipients:
            flash("Bitte mindestens einen WhatsApp-Empfänger (Telefonnummer, Gruppe oder Kanal) eintragen.")
            return redirect(url_for("profiles"))
        if "linkedin" in channels and not linkedin_organization_ids:
            flash("Bitte mindestens eine LinkedIn-Organisations-ID eintragen.")
            return redirect(url_for("profiles"))

        selected_topics = request.form.getlist("topics")
        selected_special_topics = request.form.getlist("special_topics")
        profile_data = {
            "name": request.form["name"].strip(),
            "channels": channels,
            "recipients": recipients,
            "whatsapp_recipients": whatsapp_recipients,
            "linkedin_organization_ids": linkedin_organization_ids,
            "send_time": request.form["send_time"],
            "topics": selected_topics,
            "special_topics": selected_special_topics,
            "topic_frequencies": {topic_id: request.form.get(f"frequency_{topic_id}", "daily") for topic_id in selected_topics},
            "special_topic_frequencies": {
                special_id: request.form.get(f"special_frequency_{special_id}", "daily")
                for special_id in selected_special_topics
            },
        }
        if request.form.get("new"):
            profile_id = re.sub(r"[^a-z0-9-]+", "-", profile_data["name"].lower()).strip("-") or "profil"
            current.append({"id": profile_id, **profile_data})
        else:
            profile = next(item for item in current if item["id"] == request.form["profile_id"])
            if request.form.get("delete"):
                current.remove(profile)
            else:
                profile.update(profile_data)
        save_profiles(current)
        schedule_all_profiles()
        flash("Empfängerprofile und Zeitpläne gespeichert.")
        return redirect(url_for("profiles"))
    return render_template_string(
        PROFILE_PAGE,
        profiles=current,
        topics=topics,
        special_topics=[topic.model_dump() for topic in load_special_topics()],
    )


def mutate_source(topic_id: str, source_index: str, action: str):
    topics = load_topics()
    topic = next((item for item in topics if item.id == topic_id), None)
    if topic is None:
        flash("Thema nicht gefunden.")
        return redirect(url_for("index"))
    index = int(source_index)
    if action == "delete":
        topic.sources.pop(index)
    else:
        topic.sources[index].enabled = not topic.sources[index].enabled
    save_topics(topics)
    return redirect(url_for("sources"))


@app.post("/topic/<topic_id>/toggle")
def toggle_topic(topic_id: str):
    topics = load_topics()
    topic = next((item for item in topics if item.id == topic_id), None)
    if topic is None:
        flash("Thema nicht gefunden.")
    else:
        topic.enabled = not topic.enabled
        save_topics(topics)
    return redirect(url_for("index"))


@app.post("/topic/<topic_id>/source/<source_index>/toggle")
def toggle_source(topic_id: str, source_index: str):
    return mutate_source(topic_id, source_index, "toggle")


@app.post("/topic/<topic_id>/source/<source_index>/delete")
def delete_source(topic_id: str, source_index: str):
    return mutate_source(topic_id, source_index, "delete")


def fields_for_source(source: SourceConfig | None) -> list[dict]:
    source = source or SourceConfig(name="", type="rss", url="", tier=2)
    return [
        {"name": "name", "label": "Quellenname", "value": source.name, "required": True},
        {"name": "type", "label": "Typ", "value": source.type, "kind": "select", "options": [("rss", "RSS / Atom Feed"), ("scrape", "Webseite (CSS-Selektoren)")]},
        {"name": "url", "label": "URL", "value": source.url, "required": True},
        {"name": "tier", "label": "Tier (1 = Primärquelle)", "value": str(source.tier), "required": True},
        {"name": "item_selector", "label": "Item-Selektor (nur Scrape)", "value": source.item_selector or ""},
        {"name": "title_selector", "label": "Titel-Selektor (nur Scrape)", "value": source.title_selector or ""},
        {"name": "link_selector", "label": "Link-Selektor (nur Scrape)", "value": source.link_selector or ""},
        {"name": "base_url", "label": "Basis-URL (nur Scrape)", "value": source.base_url or ""},
    ]


@app.route("/topic/<topic_id>/source/<source_index>", methods=["GET", "POST"])
def edit_source(topic_id: str, source_index: str):
    topics = load_topics()
    topic = next((item for item in topics if item.id == topic_id), None)
    if topic is None:
        flash("Thema nicht gefunden.")
        return redirect(url_for("sources"))
    existing = None if source_index == "new" else topic.sources[int(source_index)]
    if request.method == "POST":
        data = request.form.to_dict()
        try:
            source = SourceConfig(
                name=data["name"].strip(), type=data["type"], url=data["url"].strip(), tier=int(data["tier"]),
                item_selector=data.get("item_selector") or None, title_selector=data.get("title_selector") or None,
                link_selector=data.get("link_selector") or None, base_url=data.get("base_url") or None,
                enabled=existing.enabled if existing else True,
            )
            if existing:
                topic.sources[int(source_index)] = source
            else:
                topic.sources.append(source)
            save_topics(topics)
            flash("Quelle gespeichert.")
            return redirect(url_for("sources"))
        except (KeyError, ValueError) as exc:
            flash(f"Quelle konnte nicht gespeichert werden: {exc}")
    return render_template_string(FORM, title=f"Quelle in {topic.name}", fields=fields_for_source(existing))


@app.route("/topic/<topic_id>", methods=["GET", "POST"])
def edit_topic(topic_id: str):
    topics = load_topics()
    existing = None if topic_id == "new" else next((item for item in topics if item.id == topic_id), None)
    if topic_id != "new" and existing is None:
        flash("Thema nicht gefunden.")
        return redirect(url_for("index"))
    fields = [
        {"name": "id", "label": "Technische ID (z. B. arbeitsrecht)", "value": existing.id if existing else "", "required": True},
        {"name": "name", "label": "Anzeigename", "value": existing.name if existing else "", "required": True},
        {"name": "keywords", "label": "Keywords (Komma getrennt)", "value": ", ".join(existing.keywords) if existing else "", "kind": "textarea"},
        {"name": "max_items", "label": "Maximale Meldungen", "value": str(existing.max_items if existing else 5), "required": True},
        {"name": "recency_hours", "label": "Zeitraum in Stunden", "value": str(existing.recency_hours if existing else 48), "required": True},
    ]
    if request.method == "POST":
        try:
            topic = TopicConfig(
                id=request.form["id"].strip(), name=request.form["name"].strip(),
                keywords=[word.strip() for word in request.form.get("keywords", "").split(",") if word.strip()],
                max_items=int(request.form["max_items"]), recency_hours=int(request.form["recency_hours"]),
                sources=existing.sources if existing else [], enabled=existing.enabled if existing else False,
            )
            if existing:
                topics[topics.index(existing)] = topic
            else:
                topics.append(topic)
            save_topics(topics)
            flash("Thema gespeichert. Neue Themen starten pausiert, bis du sie aktivierst.")
            return redirect(url_for("index"))
        except (KeyError, ValueError) as exc:
            flash(f"Thema konnte nicht gespeichert werden: {exc}")
    return render_template_string(FORM, title="Thema bearbeiten", fields=fields)


@app.get("/run-now")
def run_now():
    subprocess.Popen([str(PYTHON), "main.py", "--run-now"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    flash("Ein Lauf wurde gestartet. Den Fortschritt findest du in logs/jura_monitor.log.")
    return redirect(url_for("index"))


@app.get("/logs")
def show_logs():
    log_file = ROOT / "logs" / "jura_monitor.log"
    content = log_file.read_text(encoding="utf-8")[-12000:] if log_file.exists() else "Noch keine Logs vorhanden."
    return "<pre style='white-space:pre-wrap;font:13px monospace;padding:24px'>" + content.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"


LINKEDIN_PAGE = """<!doctype html><html lang=de><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>LinkedIn-Verbindung</title><style>body{margin:0;background:#f5f7f8;color:#17212b;font:15px/1.5 -apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif}.nav{background:#0e2928;padding:12px 24px;display:flex;gap:10px;flex-wrap:wrap}.nav a{color:#b9d8d1;text-decoration:none;font-weight:700}.box{max-width:640px;margin:40px auto;background:#fff;border:1px solid #dbe2e7;border-radius:6px;padding:28px}h1{font:700 28px Georgia,serif;margin:0 0 8px}.hint{color:#64717d}.field{margin:18px 0}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:5px}.field input{width:100%;box-sizing:border-box;padding:10px;border:1px solid #bfcbd2;border-radius:4px;font:inherit}.button{padding:10px 14px;border:0;border-radius:4px;background:#0b6e69;color:#fff;font:inherit;font-weight:700;cursor:pointer;text-decoration:none}.secondary{background:#e6eeec;color:#07514e;margin-left:8px}</style></head><body><nav class=nav><a href=/>Übersicht</a><a href=/profiles>Empfängerprofile</a><a href=/linkedin>LinkedIn</a></nav><main class=box><h1>LinkedIn-Verbindung</h1><p class=hint>Hinterlege einen OAuth-Access-Token mit dem Scope <code>w_organization_social</code>. Die Organisations-ID wird danach je Versandprofil unter Empfängerprofile eingetragen.</p>{% with messages=get_flashed_messages() %}{% for message in messages %}<p>{{ message }}</p>{% endfor %}{% endwith %}<form method=post><div class=field><label for=token>Access-Token</label><input id=token name=access_token type=password placeholder="LinkedIn OAuth Access Token" autocomplete=off></div><div class=field><label for=version>API-Version</label><input id=version name=api_version value="{{ api_version }}" required></div><button class=button type=submit>Verbindung speichern</button><a class=\"button secondary\" href=\"{{ url_for('profiles') }}\">Zurück</a></form></main></body></html>"""


def save_env_value(key: str, value: str) -> None:
    content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"(?m)^{re.escape(key)}=.*$", content):
        content = re.sub(rf"(?m)^{re.escape(key)}=.*$", line, content)
    else:
        content = content.rstrip() + f"\n{line}\n"
    ENV_FILE.write_text(content, encoding="utf-8")


@app.route("/linkedin", methods=["GET", "POST"])
def linkedin_settings():
    settings = load_env_settings()
    if request.method == "POST":
        token = request.form.get("access_token", "").strip()
        if not token:
            flash("Bitte einen LinkedIn OAuth-Access-Token eintragen.")
        else:
            save_env_value("LINKEDIN_ACCESS_TOKEN", token)
            save_env_value("LINKEDIN_API_VERSION", request.form["api_version"].strip())
            flash("LinkedIn-Verbindung gespeichert.")
            return redirect(url_for("profiles"))
    return render_template_string(LINKEDIN_PAGE, api_version=settings.linkedin_api_version)


NAV = '<nav style="background:#0e2928;padding:12px 24px;display:flex;gap:10px;flex-wrap:wrap"><a href="/" style="color:#fff;text-decoration:none;font-weight:700">Übersicht</a><a href="/profiles" style="color:#b9d8d1;text-decoration:none">Empfängerprofile</a><a href="/linkedin" style="color:#b9d8d1;text-decoration:none">LinkedIn</a><a href="/sources" style="color:#b9d8d1;text-decoration:none">Quellenverwaltung</a></nav>'
PAGE = PAGE.replace("<body>", "<body>" + NAV)
SOURCES_PAGE = SOURCES_PAGE.replace("<body>", "<body>" + NAV)

PROFILE_PAGE = """<!doctype html><html lang=de><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Empfängerprofile</title><style>body{margin:0;background:#f5f7f8;color:#17212b;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.nav{background:#0e2928;padding:12px 24px;display:flex;gap:18px;flex-wrap:wrap}.nav a{color:#d1e4df;text-decoration:none;font-weight:700}.box{max-width:960px;margin:30px auto;padding:0 18px}.profile{background:#fff;border:1px solid #dbe2e7;border-radius:6px;padding:22px;margin:16px 0}.profile h2{font:700 22px Georgia,serif;margin:0 0 15px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:5px}.field input,.field select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #bfcbd2;border-radius:4px;font:inherit}.selection{grid-column:1/-1;border-top:1px solid #edf0f2;padding-top:14px}.choice{display:flex;align-items:center;gap:8px;padding:8px 0;flex-wrap:wrap}.choice input[type=checkbox]{width:17px;height:17px;accent-color:#0b6e69}.choice select{width:auto;min-width:135px;padding:7px}.choice .label{min-width:240px}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.button{border:0;border-radius:4px;padding:10px 14px;background:#0b6e69;color:#fff;font:inherit;font-weight:700;cursor:pointer;text-decoration:none}.secondary{background:#e6eeec;color:#07514e}.search{width:100%;box-sizing:border-box;padding:11px;border:1px solid #bfcbd2;border-radius:4px;font:inherit}.profile.hidden{display:none}.hint{color:#64717d;font-size:13px}.channels{display:flex;gap:32px;align-items:center;padding:10px 0;margin-top:4px}.channels label{font-size:14px;font-weight:600;display:inline-flex;align-items:center;gap:10px;cursor:pointer;user-select:none}.channels input[type=checkbox]{width:18px;height:18px;accent-color:#0b6e69;cursor:pointer;margin:0}@media(max-width:700px){.grid{grid-template-columns:1fr}.selection{grid-column:auto}.choice .label{min-width:0;flex:1}}</style></head><body><nav class=nav><a href="/">Übersicht</a><a href="/profiles">Empfängerprofile</a><a href="/linkedin">LinkedIn</a><a href="/sources">Quellenverwaltung</a></nav><main class=box><h1>Empfängerprofile</h1><p class=hint>Jedes Profil erhält nur die angekreuzten Bereiche. LinkedIn benötigt zusätzlich eine Organisations-ID.</p><input class=search type=search placeholder="Profile, E-Mail oder Nummern suchen ..." oninput="filterProfiles(this.value)">{% for profile in profiles %}<form class=profile data-search="{{ profile.name }} {{ profile.id }} {{ profile.recipients|join(' ') }} {{ profile.whatsapp_recipients|join(' ') }} {{ profile.linkedin_organization_ids|join(' ') }}" method=post><input type=hidden name=profile_id value="{{ profile.id }}"><h2>{{ profile.name }}</h2><div class=grid><div class=field><label for="name-{{ profile.id }}">Profilname</label><input id="name-{{ profile.id }}" name=name value="{{ profile.name }}" required></div><div class=field><label for="time-{{ profile.id }}">Startzeit</label><input id="time-{{ profile.id }}" name=send_time type=time value="{{ profile.send_time }}" required></div><div class="field selection" style="border-top:0;padding-top:0"><label>Versandkanäle</label><div class=channels><label><input type=checkbox name=channels value=email {% if 'email' in profile.channels or not profile.channels %}checked{% endif %}> E-Mail</label><label><input type=checkbox name=channels value=whatsapp {% if 'whatsapp' in profile.channels %}checked{% endif %}> WhatsApp</label><label><input type=checkbox name=channels value=linkedin {% if 'linkedin' in profile.channels %}checked{% endif %}> LinkedIn</label></div></div><div class=field data-channel-field=email><label for="recipients-{{ profile.id }}">E-Mail Empfänger (Komma getrennt)</label><input id="recipients-{{ profile.id }}" name=recipients value="{{ profile.recipients|join(', ') }}" placeholder="name@beispiel.de"></div><div class=field data-channel-field=whatsapp><label for="whatsapp-recipients-{{ profile.id }}">WhatsApp Empfänger / Kanal-IDs (Komma getrennt)</label><input id="whatsapp-recipients-{{ profile.id }}" name=whatsapp_recipients value="{{ profile.get('whatsapp_recipients', [])|join(', ') }}" placeholder="+491701234567, 120363000000000000@newsletter"></div><div class=field data-channel-field=linkedin><label for="linkedin-organizations-{{ profile.id }}">LinkedIn Organisations-ID (Komma getrennt)</label><input id="linkedin-organizations-{{ profile.id }}" name=linkedin_organization_ids value="{{ profile.get('linkedin_organization_ids', [])|join(', ') }}" placeholder="123456789"></div><div class=selection><strong>Nachrichten</strong>{% for topic in topics %}<label class=choice><input type=checkbox name=topics value="{{ topic.id }}" {% if topic.id in profile.topics %}checked{% endif %}><span class=label>{{ topic.name }}</span><select name="frequency_{{ topic.id }}" {% if topic.id not in profile.topics %}hidden{% endif %}><option value=daily {% if profile.topic_frequencies.get(topic.id, 'daily')=='daily' %}selected{% endif %}>täglich</option><option value=weekly {% if profile.topic_frequencies.get(topic.id, 'daily')=='weekly' %}selected{% endif %}>wöchentlich</option><option value=monthly {% if profile.topic_frequencies.get(topic.id, 'daily')=='monthly' %}selected{% endif %}>monatlich</option></select></label>{% endfor %}</div><div class=selection><strong>Spezialthemen</strong>{% for special in special_topics %}<label class=choice title="{{ special.description }}"><input type=checkbox name=special_topics value="{{ special.id }}" {% if special.id in profile.special_topics %}checked{% endif %}><span class=label>{{ special.name }}</span><select name="special_frequency_{{ special.id }}" {% if special.id not in profile.special_topics %}hidden{% endif %}><option value=daily {% if profile.special_topic_frequencies.get(special.id, 'daily')=='daily' %}selected{% endif %}>täglich</option><option value=weekly {% if profile.special_topic_frequencies.get(special.id, 'daily')=='weekly' %}selected{% endif %}>wöchentlich</option><option value=monthly {% if profile.special_topic_frequencies.get(special.id, 'daily')=='monthly' %}selected{% endif %}>monatlich</option></select></label>{% endfor %}</div></div><div class=actions><button class=button type=submit>Profil speichern</button><button class="button secondary" name=delete value=1 type=submit>Profil löschen</button></div></form>{% endfor %}<form class=profile method=post><input type=hidden name=new value=1><h2>Neues Profil</h2><div class=grid><div class=field><label for=new-name>Name</label><input id=new-name name=name placeholder="z. B. LinkedIn Jura News" required></div><div class=field><label for=new-time>Startzeit</label><input id=new-time name=send_time type=time value=07:00 required></div><div class="field selection" style="border-top:0;padding-top:0"><label>Versandkanäle</label><div class=channels><label><input type=checkbox name=channels value=email checked> E-Mail</label><label><input type=checkbox name=channels value=whatsapp> WhatsApp</label><label><input type=checkbox name=channels value=linkedin> LinkedIn</label></div></div><div class=field data-channel-field=email><label for=new-recipients>E-Mail Empfänger</label><input id=new-recipients name=recipients placeholder="name@beispiel.de"></div><div class=field data-channel-field=whatsapp><label for=new-whatsapp-recipients>WhatsApp Empfänger / Channel-IDs</label><input id=new-whatsapp-recipients name=whatsapp_recipients placeholder="+491701234567, 120363000000000000@newsletter"></div><div class=field data-channel-field=linkedin><label for=new-linkedin-organizations>LinkedIn Organisations-ID</label><input id=new-linkedin-organizations name=linkedin_organization_ids placeholder="123456789"></div><div class=selection><strong>Nachrichten</strong>{% for topic in topics %}<label class=choice><input type=checkbox name=topics value="{{ topic.id }}"><span class=label>{{ topic.name }}</span><select name="frequency_{{ topic.id }}" hidden><option value=daily>täglich</option><option value=weekly>wöchentlich</option><option value=monthly>monatlich</option></select></label>{% endfor %}</div><div class=selection><strong>Spezialthemen</strong>{% for special in special_topics %}<label class=choice title="{{ special.description }}"><input type=checkbox name=special_topics value="{{ special.id }}"><span class=label>{{ special.name }}</span><select name="special_frequency_{{ special.id }}" hidden><option value=daily>täglich</option><option value=weekly>wöchentlich</option><option value=monthly>monatlich</option></select></label>{% endfor %}</div></div><div class=actions><button class=button type=submit>Profil hinzufügen</button></div></form></main><script>document.querySelectorAll('.choice input[type=checkbox]').forEach(box=>{box.addEventListener('change',()=>{const select=box.parentElement.querySelector('select');if(select)select.hidden=!box.checked})});function updateChannelFields(form){const emailBox=form.querySelector('input[name=channels][value=email]');const waBox=form.querySelector('input[name=channels][value=whatsapp]');const linkedinBox=form.querySelector('input[name=channels][value=linkedin]');const emailField=form.querySelector('[data-channel-field=email]');const waField=form.querySelector('[data-channel-field=whatsapp]');const linkedinField=form.querySelector('[data-channel-field=linkedin]');if(emailField)emailField.style.display=emailBox&&emailBox.checked?'block':'none';if(waField)waField.style.display=waBox&&waBox.checked?'block':'none';if(linkedinField)linkedinField.style.display=linkedinBox&&linkedinBox.checked?'block':'none'}document.querySelectorAll('.profile').forEach(form=>{form.querySelectorAll('input[name=channels]').forEach(box=>box.addEventListener('change',()=>updateChannelFields(form)));updateChannelFields(form)});function filterProfiles(value){const term=value.toLowerCase().trim();document.querySelectorAll('.profile[data-search]').forEach(profile=>profile.classList.toggle('hidden',term&&!profile.dataset.search.toLowerCase().includes(term)))}</script></body></html>"""


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
