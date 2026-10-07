from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

_RE_PANE_ONGOING = re.compile(r'id="is-TrafficInfos-Disruption-List_Ongoing"')
_RE_PANE_TOCOME = re.compile(r'id="is-TrafficInfos-Disruption-List_ToCome"')
_RE_LINK = re.compile(
    r'data-target="#([^"]+)"[\s\S]*?data-line-id="([^"]+)"\s+data-line-short-name="([^"]+)"[\s\S]*?'
    r'is-Disruption-State_(\w+)',
)
_RE_MODAL = re.compile(r'<div class="is-Modal is-fade" id="([^"]+)"')
_RE_ITEM = re.compile(r'<div class="is-Disruption-Item-Header-State">')
_RE_TITLE = re.compile(r'class="is-Disruption-Item-Header-Title">(.*?)</p>', re.S)
_RE_EFFECT = re.compile(r'is-Disruption-Effect-(\w+)')
_RE_PERIOD = re.compile(r'Période d(?:&#039;|\')application</p>\s*<p class="is-Disruptions-Details-Item">(.*?)</p>', re.S)
_RE_DATE = re.compile(r'(\d{2})/(\d{2})/(\d{4})(?:\s*à\s*(\d{2}):(\d{2}))?')
_RE_PROBLEMS = re.compile(r'<div class="is-Disruptions-Details-Problems">(.*?)</div>', re.S)
_RE_PROBLEM_ITEM = re.compile(r'<span class="is-Disruptions-Details-Problems-Item">(.*?)</span>', re.S)
_RE_LINES_BLOCK = re.compile(r'<div class="is-Disruptions-Details-Lines">(.*?)</div>\s*<p class="is-Disruptions-Details-Problems-Item">', re.S)
_RE_LINE_BADGE = re.compile(r'Ligne </span>\s*([^<\s]+)')
_RE_DIRECTION = re.compile(r'<span class="direction">(.*?)</span>', re.S)
_RE_BODY = re.compile(r'<p class="is-Disruptions-Details-Problems-Item">(.*)<p class="is-Disruption-Item-Content-UpdateDate', re.S)
_RE_UPDATE = re.compile(r'is-Disruption-Item-Content-UpdateDate[^>]*>(.*?)</p>', re.S)
_RE_TAG = re.compile(r'<[^>]+>')
_RE_STYLE_ATTR = re.compile(r'\s+(?:style|class|lang|dir)="[^"]*"', re.I)
_RE_SPAN = re.compile(r'</?span[^>]*>', re.I)
_RE_EMPTY_P = re.compile(r'<p>\s*(?:&nbsp;|\s)*</p>', re.I)
_RE_TAGS_INTERDITS = re.compile(r'</?(?!p\b|br\b|strong\b|b\b|em\b|i\b|ul\b|ol\b|li\b|a\b)[a-z][^>]*>', re.I)


def _texte(fragment: str) -> str:
    return html.unescape(re.sub(r'\s+', ' ', _RE_TAG.sub(' ', fragment))).strip()


def _corps(fragment: str) -> str:
    corps = fragment.strip()
    if corps.endswith("</p>"):
        corps = corps[: -len("</p>")]
    corps = _RE_SPAN.sub("", corps)
    corps = _RE_STYLE_ATTR.sub("", corps)
    corps = _RE_TAGS_INTERDITS.sub("", corps)
    corps = _RE_EMPTY_P.sub("", corps)
    return re.sub(r'\s+', ' ', corps).strip()


def _dates(periode: str, fuseau: ZoneInfo) -> tuple[str | None, str | None]:
    trouvees = []
    for jj, mm, aaaa, hh, mn in _RE_DATE.findall(periode):
        try:
            dt = datetime(int(aaaa), int(mm), int(jj), int(hh or 0), int(mn or 0), tzinfo=fuseau)
        except ValueError:
            continue
        trouvees.append(dt.isoformat())
    texte = _texte(periode).lower()
    if len(trouvees) >= 2:
        return trouvees[0], trouvees[1]
    if len(trouvees) == 1:
        if "jusqu" in texte or texte.startswith("au "):
            return None, trouvees[0]
        return trouvees[0], None
    return None, None


def analyser_infotrafic(contenu: str, fuseau: ZoneInfo) -> list[dict]:
    debut_ongoing = _RE_PANE_ONGOING.search(contenu)
    debut_tocome = _RE_PANE_TOCOME.search(contenu)
    if not debut_ongoing:
        return []
    fin_ongoing = debut_tocome.start() if debut_tocome else len(contenu)
    panes = [("en_cours", contenu[debut_ongoing.start():fin_ongoing])]
    if debut_tocome:
        panes.append(("a_venir", contenu[debut_tocome.start():]))

    messages: dict[str, dict] = {}
    for etat, pane in panes:
        gravites: dict[str, tuple[str, str, str]] = {}
        for cible, id_ligne, num, gravite in _RE_LINK.findall(pane):
            gravites[cible] = (id_ligne, num, gravite)
        modaux = list(_RE_MODAL.finditer(pane))
        for index, modal in enumerate(modaux):
            fin = modaux[index + 1].start() if index + 1 < len(modaux) else len(pane)
            bloc = pane[modal.start():fin]
            id_modal = modal.group(1)
            ligne_modal = gravites.get(id_modal)
            items = _RE_ITEM.split(bloc)[1:]
            for item in items:
                titre_m = _RE_TITLE.search(item)
                titre = _texte(titre_m.group(1)).rstrip(":").strip() if titre_m else "Info trafic"
                effet_m = _RE_EFFECT.search(item)
                periode_m = _RE_PERIOD.search(item)
                debut, fin_periode = _dates(periode_m.group(1), fuseau) if periode_m else (None, None)
                problemes_m = _RE_PROBLEMS.search(item)
                causes = [_texte(c) for c in _RE_PROBLEM_ITEM.findall(problemes_m.group(1))] if problemes_m else []
                lignes_m = _RE_LINES_BLOCK.search(item)
                lignes = [html.unescape(l) for l in _RE_LINE_BADGE.findall(lignes_m.group(1))] if lignes_m else []
                sens = sorted({_texte(d) for d in _RE_DIRECTION.findall(lignes_m.group(1))}) if lignes_m else []
                if not lignes and ligne_modal:
                    lignes = [ligne_modal[1]]
                corps_m = _RE_BODY.search(item)
                corps = _corps(corps_m.group(1)) if corps_m else ""
                maj_m = _RE_UPDATE.search(item)
                mise_a_jour = _texte(maj_m.group(1)) if maj_m else ""
                gravite = ligne_modal[2] if ligne_modal else "INFO"
                cle = hashlib.sha1(f"{titre}|{debut}|{fin_periode}|{_texte(corps)}".encode()).hexdigest()[:12]
                message = messages.get(cle)
                if message is None:
                    message = {
                        "id": f"infotrafic-{cle}",
                        "type": "infotrafic",
                        "titre": titre,
                        "corps": corps,
                        "lignes": [],
                        "etat": etat,
                        "gravite": gravite,
                        "effet": effet_m.group(1) if effet_m else None,
                        "causes": causes,
                        "sens": " / ".join(sens),
                        "debut": debut,
                        "fin": fin_periode,
                        "mise_a_jour": mise_a_jour,
                        "source": "grandole-mobilites.fr",
                    }
                    messages[cle] = message
                for num in lignes:
                    if num not in message["lignes"]:
                        message["lignes"].append(num)
                if gravite == "WARN":
                    message["gravite"] = "WARN"
    return list(messages.values())
