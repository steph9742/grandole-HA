from __future__ import annotations

import csv
import io
import math
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .const import (
    AGE_MAX_FLUX,
    AGE_MAX_MISE_A_JOUR,
    GRACE_PASSAGE,
    HORIZON_PASSAGES,
    MARGE_APRES_COURSE,
    MARGE_AVANT_COURSE,
    RAYON_A_QUAI,
    RAYON_PROXIMITE,
    RETARD_MESSAGE,
    RETARD_PERTURBATION,
    TOLERANCE_HEURE_PREVUE,
)

JOURS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
RANG_ETAT = {0: 0, 1: 0, 3: 0, 2: 1, 4: 2, 5: 3, 6: 4}


def normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold().strip()


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _secondes(hms: str) -> int:
    parties = hms.strip().split(":")
    if len(parties) != 3:
        raise ValueError(hms)
    return int(parties[0]) * 3600 + int(parties[1]) * 60 + int(parties[2])


def _couleur(valeur: str | None, defaut: str) -> str:
    v = (valeur or "").strip().lstrip("#").upper()
    return f"#{v}" if len(v) == 6 else defaut


def _hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _libelle_temps(secondes: int) -> str:
    if secondes < 60:
        return "< 1 min"
    return f"{secondes // 60} min"


@dataclass(slots=True)
class Arret:
    id: str
    nom: str
    latitude: float
    longitude: float
    accessible: bool


@dataclass(slots=True)
class Ligne:
    id: str
    num: str
    nom: str
    couleur_fond: str
    couleur_texte: str
    ordre: int


@dataclass(slots=True)
class Course:
    id: str
    id_ligne: str
    id_service: str
    destination: str
    sens_aller: bool
    accessible: bool
    arrets: list[str] = field(default_factory=list)
    sequences: list[int] = field(default_factory=list)
    arrivees: list[int] = field(default_factory=list)
    departs: list[int] = field(default_factory=list)
    destinations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArretMaj:
    sequence: int | None
    id_arret: str | None
    retard: int | None
    heure: int | None
    saute: bool


@dataclass(slots=True)
class MiseAJourCourse:
    id_course: str
    id_ligne: str
    date_debut: str
    horodatage: int
    annulee: bool
    vehicule: str | None
    retard_course: int | None
    par_sequence: dict[int, ArretMaj] = field(default_factory=dict)
    par_arret: dict[str, ArretMaj] = field(default_factory=dict)


@dataclass(slots=True)
class PositionVehicule:
    id: str
    label: str | None
    id_course: str | None
    id_ligne: str | None
    latitude: float
    longitude: float
    cap: float | None
    horodatage: int


@dataclass(slots=True)
class TempsReel:
    horodatage: int = 0
    courses: dict[str, MiseAJourCourse] = field(default_factory=dict)
    vehicules: list[PositionVehicule] = field(default_factory=list)
    disponible: bool = False
    derniere_donnee: int = 0

    def age(self, maintenant_ts: float) -> int | None:
        if not self.derniere_donnee:
            return None
        return max(0, int(maintenant_ts - self.derniere_donnee))

    def frais(self, maintenant_ts: float) -> bool:
        age = self.age(maintenant_ts)
        return self.disponible and age is not None and age <= AGE_MAX_FLUX

    def vehicule_de_course(self, id_course: str) -> PositionVehicule | None:
        for v in self.vehicules:
            if v.id_course == id_course:
                return v
        return None


@dataclass(slots=True)
class Prediction:
    theorique: datetime
    prevu: datetime
    fiable: bool
    retard: int | None
    annule: bool
    saute: bool
    vehicule: str | None


class Reseau:
    def __init__(self, version: str) -> None:
        self.version = version
        self.fuseau = ZoneInfo("Europe/Paris")
        self.nom_agence = ""
        self.arrets: dict[str, Arret] = {}
        self.arrets_par_nom: dict[str, list[Arret]] = {}
        self.lignes: dict[str, Ligne] = {}
        self.courses: dict[str, Course] = {}
        self.index_arret: dict[str, list[tuple[int, str, int]]] = {}
        self.calendrier: dict[str, tuple[str, str, tuple[bool, ...]]] = {}
        self.exceptions: dict[str, dict[str, str]] = {}
        self.debut_validite = ""
        self.fin_validite = ""
        self._cache_services: dict[date, frozenset[str]] = {}

    @classmethod
    def depuis_zip(cls, contenu: bytes, version: str) -> "Reseau":
        reseau = cls(version)
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            noms = {n.split("/")[-1]: n for n in z.namelist()}

            def lire(nom: str) -> list[dict]:
                if nom not in noms:
                    return []
                with z.open(noms[nom]) as f:
                    texte = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
                    return [
                        {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in ligne.items() if k}
                        for ligne in csv.DictReader(texte)
                    ]

            for a in lire("agency.txt"):
                if a.get("agency_timezone"):
                    try:
                        reseau.fuseau = ZoneInfo(a["agency_timezone"])
                    except Exception:
                        pass
                reseau.nom_agence = a.get("agency_name", "")
                break

            for s in lire("stops.txt"):
                if s.get("location_type", "0") not in ("", "0"):
                    continue
                try:
                    arret = Arret(
                        id=s["stop_id"],
                        nom=s.get("stop_name", "").strip(),
                        latitude=float(s["stop_lat"]),
                        longitude=float(s["stop_lon"]),
                        accessible=s.get("wheelchair_boarding", "0") == "1",
                    )
                except (KeyError, ValueError):
                    continue
                reseau.arrets[arret.id] = arret
                reseau.arrets_par_nom.setdefault(arret.nom, []).append(arret)

            for r in lire("routes.txt"):
                if not r.get("route_id"):
                    continue
                try:
                    ordre = int(r.get("route_sort_order") or 0)
                except ValueError:
                    ordre = 0
                num = r.get("route_short_name") or r.get("route_id")
                reseau.lignes[r["route_id"]] = Ligne(
                    id=r["route_id"],
                    num=num,
                    nom=r.get("route_long_name", ""),
                    couleur_fond=_couleur(r.get("route_color"), "#D82080"),
                    couleur_texte=_couleur(r.get("route_text_color"), "#FFFFFF"),
                    ordre=ordre,
                )

            for c in lire("calendar.txt"):
                if not c.get("service_id"):
                    continue
                reseau.calendrier[c["service_id"]] = (
                    c.get("start_date", ""),
                    c.get("end_date", ""),
                    tuple(c.get(j, "0") == "1" for j in JOURS),
                )

            for e in lire("calendar_dates.txt"):
                if e.get("service_id") and e.get("date"):
                    reseau.exceptions.setdefault(e["date"], {})[e["service_id"]] = e.get("exception_type", "1")

            for t in lire("trips.txt"):
                if not t.get("trip_id") or t.get("route_id") not in reseau.lignes:
                    continue
                reseau.courses[t["trip_id"]] = Course(
                    id=t["trip_id"],
                    id_ligne=t["route_id"],
                    id_service=t.get("service_id", ""),
                    destination=t.get("trip_headsign", ""),
                    sens_aller=t.get("direction_id", "0") != "1",
                    accessible=t.get("wheelchair_accessible", "0") == "1",
                )

            temporaire: dict[str, list[tuple[int, str, int, int, str]]] = defaultdict(list)
            for st in lire("stop_times.txt"):
                course = reseau.courses.get(st.get("trip_id", ""))
                if course is None or st.get("stop_id") not in reseau.arrets:
                    continue
                try:
                    arr = _secondes(st.get("arrival_time") or st["departure_time"])
                    dep = _secondes(st.get("departure_time") or st["arrival_time"])
                    seq = int(st["stop_sequence"])
                except (KeyError, ValueError):
                    continue
                temporaire[course.id].append((seq, st["stop_id"], arr, dep, st.get("stop_headsign", "")))

            for id_course, liste in temporaire.items():
                liste.sort(key=lambda x: x[0])
                course = reseau.courses[id_course]
                for idx, (seq, id_arret, arr, dep, headsign) in enumerate(liste):
                    course.sequences.append(seq)
                    course.arrets.append(id_arret)
                    course.arrivees.append(arr)
                    course.departs.append(dep)
                    course.destinations.append(headsign)
                    reseau.index_arret.setdefault(id_arret, []).append((dep, id_course, idx))

            for id_course in list(reseau.courses):
                if not reseau.courses[id_course].arrets:
                    del reseau.courses[id_course]

            for liste in reseau.index_arret.values():
                liste.sort(key=lambda x: x[0])

        dates = [d for c in reseau.calendrier.values() for d in (c[0], c[1]) if d]
        dates += list(reseau.exceptions)
        if dates:
            reseau.debut_validite = min(dates)
            reseau.fin_validite = max(dates)
        return reseau

    def services_actifs(self, jour: date) -> frozenset[str]:
        cache = self._cache_services.get(jour)
        if cache is not None:
            return cache
        cle = jour.strftime("%Y%m%d")
        actifs: set[str] = set()
        for id_service, (debut, fin, jours) in self.calendrier.items():
            if debut <= cle <= fin and jours[jour.weekday()]:
                actifs.add(id_service)
        for id_service, type_exception in self.exceptions.get(cle, {}).items():
            if type_exception == "1":
                actifs.add(id_service)
            else:
                actifs.discard(id_service)
        resultat = frozenset(actifs)
        if len(self._cache_services) > 8:
            self._cache_services.clear()
        self._cache_services[jour] = resultat
        return resultat

    def base_jour(self, jour: date) -> datetime:
        return datetime.combine(jour, time(12), tzinfo=self.fuseau) - timedelta(hours=12)

    def jours_candidats(self, maintenant: datetime) -> list[tuple[date, datetime]]:
        local = maintenant.astimezone(self.fuseau)
        jours = [local.date() - timedelta(days=1), local.date()]
        return [(j, self.base_jour(j)) for j in jours]

    def noms_arrets(self) -> list[str]:
        return sorted(self.arrets_par_nom, key=normaliser)

    def resoudre_nom(self, nom: str) -> str | None:
        if nom in self.arrets_par_nom:
            return nom
        cible = normaliser(nom)
        if not cible:
            return None
        for n in self.arrets_par_nom:
            if normaliser(n) == cible:
                return n
        prefixes = [n for n in self.arrets_par_nom if normaliser(n).startswith(cible)]
        if prefixes:
            return sorted(prefixes, key=normaliser)[0]
        contenus = [n for n in self.arrets_par_nom if cible in normaliser(n)]
        if contenus:
            return sorted(contenus, key=normaliser)[0]
        return None

    def ids_arrets(self, nom: str) -> list[str]:
        return [a.id for a in self.arrets_par_nom.get(nom, [])]

    def chercher_arrets(self, texte: str, limite: int) -> list[dict]:
        requete = normaliser(texte)
        resultats = [self.description_arret(nom) for nom in self.noms_arrets()]
        if not requete:
            return resultats[:limite]
        debut, mot, contient = [], [], []
        for a in resultats:
            nom = normaliser(a["nom"])
            if nom.startswith(requete):
                debut.append(a)
            elif any(m.startswith(requete) for m in nom.replace("-", " ").split()):
                mot.append(a)
            elif requete in nom:
                contient.append(a)
        return (debut + mot + contient)[:limite]

    def description_arret(self, nom: str) -> dict:
        arrets = self.arrets_par_nom.get(nom, [])
        lignes = sorted(
            {self.lignes[c.id_ligne].num for a in arrets for (_, id_course, _) in self.index_arret.get(a.id, [])
             for c in (self.courses.get(id_course),) if c},
            key=lambda n: (len(n), n),
        )
        return {
            "nom": nom,
            "latitude": arrets[0].latitude if arrets else None,
            "longitude": arrets[0].longitude if arrets else None,
            "accessible": any(a.accessible for a in arrets),
            "quais": len(arrets),
            "lignes": lignes,
        }

    def lignes_arret(self, nom: str) -> list[Ligne]:
        ids: set[str] = set()
        for id_arret in self.ids_arrets(nom):
            for (_, id_course, _) in self.index_arret.get(id_arret, []):
                course = self.courses.get(id_course)
                if course:
                    ids.add(course.id_ligne)
        return sorted((self.lignes[i] for i in ids if i in self.lignes), key=lambda l: (l.ordre, l.num))

    def sens_ligne_arret(self, nom: str, id_ligne: str) -> list[dict]:
        compteur: dict[bool, Counter] = {True: Counter(), False: Counter()}
        for id_arret in self.ids_arrets(nom):
            for (_, id_course, idx) in self.index_arret.get(id_arret, []):
                course = self.courses.get(id_course)
                if course is None or course.id_ligne != id_ligne or idx == len(course.arrets) - 1:
                    continue
                compteur[course.sens_aller][course.destinations[idx] or course.destination] += 1
        resultat = []
        for sens_aller in (True, False):
            if compteur[sens_aller]:
                destinations = [d for d, _ in compteur[sens_aller].most_common()]
                resultat.append({
                    "sens_aller": sens_aller,
                    "destination": destinations[0],
                    "destinations": destinations,
                })
        return resultat

    def lignes_triees(self) -> list[Ligne]:
        return sorted(self.lignes.values(), key=lambda l: (l.ordre, l.num))

    def arrets_proches(self, latitude: float, longitude: float, max_stops: int, rayon: float = RAYON_PROXIMITE) -> list[dict]:
        meilleurs: dict[str, float] = {}
        for arret in self.arrets.values():
            d = distance_m(latitude, longitude, arret.latitude, arret.longitude)
            if d <= rayon and (arret.nom not in meilleurs or d < meilleurs[arret.nom]):
                meilleurs[arret.nom] = d
        tries = sorted(meilleurs.items(), key=lambda x: x[1])[:max_stops]
        return [{"nom": nom, "distance": round(d), "ids": self.ids_arrets(nom)} for nom, d in tries]

    def _maj_valide(self, maj: MiseAJourCourse | None, course: Course, base: datetime) -> bool:
        if maj is None:
            return False
        if maj.date_debut:
            return maj.date_debut == base.date().strftime("%Y%m%d")
        debut = base.timestamp() + course.departs[0] - MARGE_AVANT_COURSE
        fin = base.timestamp() + course.arrivees[-1] + MARGE_APRES_COURSE
        return debut <= maj.horodatage <= fin

    def _arret_maj(self, maj: MiseAJourCourse, course: Course, idx: int) -> ArretMaj | None:
        seq = course.sequences[idx]
        direct = maj.par_sequence.get(seq)
        if direct is None and not maj.par_sequence:
            direct = maj.par_arret.get(course.arrets[idx])
        if direct is not None:
            return direct
        precedentes = [s for s in maj.par_sequence if s < seq]
        if precedentes:
            return maj.par_sequence[max(precedentes)]
        suivantes = [s for s in maj.par_sequence if s > seq]
        if suivantes:
            candidate = maj.par_sequence[min(suivantes)]
            return ArretMaj(seq, None, candidate.retard, None, False)
        return None

    def prediction(self, course: Course, base: datetime, idx: int, temps_reel: TempsReel | None) -> Prediction:
        theorique = base + timedelta(seconds=course.departs[idx])
        maj = temps_reel.courses.get(course.id) if temps_reel else None
        if not self._maj_valide(maj, course, base):
            return Prediction(theorique, theorique, False, None, False, False, None)
        assert maj is not None
        if maj.annulee:
            return Prediction(theorique, theorique, True, None, True, False, maj.vehicule)
        arret_maj = self._arret_maj(maj, course, idx)
        retard: int | None = None
        prevu = theorique
        saute = False
        if arret_maj is not None:
            saute = arret_maj.saute
            if arret_maj.heure is not None and arret_maj.sequence == course.sequences[idx] and \
                    abs(arret_maj.heure - theorique.timestamp()) <= TOLERANCE_HEURE_PREVUE:
                prevu = datetime.fromtimestamp(arret_maj.heure, self.fuseau)
                retard = int(prevu.timestamp() - theorique.timestamp())
            elif arret_maj.retard is not None:
                retard = arret_maj.retard
                prevu = theorique + timedelta(seconds=retard)
        if retard is None and maj.retard_course is not None:
            retard = maj.retard_course
            prevu = theorique + timedelta(seconds=retard)
        if retard is None:
            retard = 0
        return Prediction(theorique, prevu, True, retard, False, saute, maj.vehicule)

    def _numero_vehicule(self, course: Course, prediction: Prediction, temps_reel: TempsReel | None) -> str | None:
        if temps_reel:
            position = temps_reel.vehicule_de_course(course.id)
            if position is not None:
                return position.label or position.id
        return prediction.vehicule

    def _passage(self, arret: Arret, course: Course, idx: int, prediction: Prediction, maintenant: datetime, temps_reel: TempsReel | None) -> dict:
        ligne = self.lignes[course.id_ligne]
        secondes = max(0, int(prediction.prevu.timestamp() - maintenant.timestamp()))
        libelle = _libelle_temps(secondes)
        return {
            "idLigne": ligne.id,
            "numLignePublic": ligne.num,
            "nomLigne": ligne.nom,
            "couleurFond": ligne.couleur_fond,
            "couleurTexte": ligne.couleur_texte,
            "destination": course.destinations[idx] or course.destination,
            "precisionDestination": "",
            "temps": libelle,
            "tempsHTML": libelle,
            "tempsEnSeconde": secondes,
            "typeDeTemps": 0,
            "fiable": prediction.fiable,
            "retard": prediction.retard,
            "heure": _hhmm(prediction.prevu.astimezone(self.fuseau)),
            "heureTheorique": _hhmm(prediction.theorique.astimezone(self.fuseau)),
            "numVehicule": self._numero_vehicule(course, prediction, temps_reel),
            "modeTransport": 0,
            "accessibiliteVehicule": 1 if course.accessible else 0,
            "accessibiliteArret": 1 if arret.accessible else 0,
            "idArret": arret.id,
            "nomExact": arret.nom,
            "latitude": arret.latitude,
            "longitude": arret.longitude,
            "sensAller": course.sens_aller,
            "idCourse": course.id,
        }

    def passages(
        self,
        ids_arrets: list[str],
        maintenant: datetime,
        temps_reel: TempsReel | None,
        nb: int,
        id_ligne: str | None = None,
        sens_aller: bool | None = None,
        horizon: int = HORIZON_PASSAGES,
    ) -> list[dict]:
        candidats: list[tuple[datetime, dict]] = []
        limite_basse = maintenant.timestamp() - GRACE_PASSAGE
        limite_haute = maintenant.timestamp() + horizon
        for jour, base in self.jours_candidats(maintenant):
            actifs = self.services_actifs(jour)
            base_ts = base.timestamp()
            for id_arret in ids_arrets:
                arret = self.arrets.get(id_arret)
                if arret is None:
                    continue
                for (depart, id_course, idx) in self.index_arret.get(id_arret, []):
                    if base_ts + depart > limite_haute + TOLERANCE_HEURE_PREVUE:
                        break
                    course = self.courses[id_course]
                    if course.id_service not in actifs or idx == len(course.arrets) - 1:
                        continue
                    if id_ligne is not None and course.id_ligne != id_ligne:
                        continue
                    if sens_aller is not None and course.sens_aller != sens_aller:
                        continue
                    if base_ts + depart < limite_basse - TOLERANCE_HEURE_PREVUE:
                        continue
                    prediction = self.prediction(course, base, idx, temps_reel)
                    if prediction.annule or prediction.saute:
                        continue
                    ts = prediction.prevu.timestamp()
                    if ts < limite_basse or ts > limite_haute:
                        continue
                    candidats.append((prediction.prevu, self._passage(arret, course, idx, prediction, maintenant, temps_reel)))
        candidats.sort(key=lambda x: x[0])
        compteur: Counter = Counter()
        resultat: list[dict] = []
        for _, passage in candidats:
            cle = (passage["idLigne"], passage["sensAller"])
            if compteur[cle] >= nb:
                continue
            compteur[cle] += 1
            resultat.append(passage)
        return resultat

    def instances_du_jour(self, maintenant: datetime, id_ligne: str | None = None) -> list[tuple[Course, datetime]]:
        resultat: list[tuple[Course, datetime]] = []
        candidats = self.jours_candidats(maintenant)
        debut_jour = candidats[-1][1].timestamp()
        for jour, base in candidats:
            actifs = self.services_actifs(jour)
            base_ts = base.timestamp()
            for course in self.courses.values():
                if course.id_service not in actifs:
                    continue
                if id_ligne is not None and course.id_ligne != id_ligne:
                    continue
                if base_ts + course.arrivees[-1] + MARGE_APRES_COURSE < debut_jour:
                    continue
                resultat.append((course, base))
        return resultat

    def _prochain_index(self, course: Course, base: datetime, maintenant: datetime, temps_reel: TempsReel | None) -> tuple[int, Prediction]:
        derniere: Prediction | None = None
        for idx in range(len(course.arrets)):
            prediction = self.prediction(course, base, idx, temps_reel)
            derniere = prediction
            if prediction.prevu.timestamp() >= maintenant.timestamp():
                return idx, prediction
        assert derniere is not None
        return len(course.arrets) - 1, derniere

    def etat_lignes(self, maintenant: datetime, temps_reel: TempsReel | None, infotrafic: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
        infotrafic = infotrafic or []
        infos_par_ligne: dict[str, list[dict]] = defaultdict(list)
        for info in infotrafic:
            for num in info.get("lignes", []):
                infos_par_ligne[str(num)].append(info)
        instances = self.instances_du_jour(maintenant)
        par_ligne: dict[str, list[tuple[Course, datetime]]] = defaultdict(list)
        for course, base in instances:
            par_ligne[course.id_ligne].append((course, base))
        vehicules_par_ligne: Counter = Counter()
        if temps_reel:
            for v in temps_reel.vehicules:
                id_ligne = v.id_ligne
                if not id_ligne and v.id_course and v.id_course in self.courses:
                    id_ligne = self.courses[v.id_course].id_ligne
                if id_ligne:
                    vehicules_par_ligne[id_ligne] += 1
        now_ts = maintenant.timestamp()
        etats: list[dict] = []
        messages: list[dict] = []
        for ligne in self.lignes_triees():
            en_cours = 0
            a_venir = 0
            annulees = 0
            restantes_annulees = 0
            restantes = 0
            arrets_sautes = 0
            retard_max: int | None = None
            prochain_depart: datetime | None = None
            for course, base in par_ligne.get(ligne.id, []):
                debut = self.prediction(course, base, 0, temps_reel)
                fin = self.prediction(course, base, len(course.arrets) - 1, temps_reel)
                debut_ts = debut.prevu.timestamp()
                fin_ts = fin.prevu.timestamp()
                if debut.annule:
                    if fin_ts >= now_ts - 3600:
                        annulees += 1
                        messages.append({
                            "id": f"annulation-{course.id}-{base.date().isoformat()}",
                            "type": "annulation",
                            "titre": f"Ligne {ligne.num} : course de {_hhmm(debut.theorique.astimezone(self.fuseau))} vers {course.destination} annulée",
                            "corps": f"La course de {_hhmm(debut.theorique.astimezone(self.fuseau))} au départ de {self.arrets[course.arrets[0]].nom} vers {course.destination} est annulée.",
                            "lignes": [ligne.num],
                            "idCourse": course.id,
                        })
                    if debut_ts >= now_ts - 60:
                        restantes_annulees += 1
                        restantes += 1
                    continue
                if debut_ts >= now_ts - 60:
                    restantes += 1
                if debut_ts - 60 <= now_ts <= fin_ts + 60:
                    en_cours += 1
                    idx, prediction = self._prochain_index(course, base, maintenant, temps_reel)
                    if prediction.fiable and prediction.retard is not None:
                        if retard_max is None or prediction.retard > retard_max:
                            retard_max = prediction.retard
                        if prediction.retard >= RETARD_MESSAGE:
                            minutes = prediction.retard // 60
                            vehicule = self._numero_vehicule(course, prediction, temps_reel)
                            details = f" (véhicule {vehicule})" if vehicule else ""
                            messages.append({
                                "id": f"retard-{course.id}-{base.date().isoformat()}",
                                "type": "retard",
                                "titre": f"Ligne {ligne.num} : {minutes} min de retard vers {course.destination}",
                                "corps": f"La course de {_hhmm(debut.theorique.astimezone(self.fuseau))} vers {course.destination}{details} accuse {minutes} min de retard à l'arrêt {self.arrets[course.arrets[idx]].nom}.",
                                "lignes": [ligne.num],
                                "idCourse": course.id,
                            })
                    if prediction.fiable:
                        maj = temps_reel.courses.get(course.id) if temps_reel else None
                        if maj is not None:
                            for seq, am in maj.par_sequence.items():
                                if am.saute and seq in course.sequences:
                                    i = course.sequences.index(seq)
                                    if course.departs[i] + base.timestamp() >= now_ts - 60:
                                        arrets_sautes += 1
                                        messages.append({
                                            "id": f"saut-{course.id}-{seq}-{base.date().isoformat()}",
                                            "type": "arret_non_desservi",
                                            "titre": f"Ligne {ligne.num} : arrêt {self.arrets[course.arrets[i]].nom} non desservi",
                                            "corps": f"La course de {_hhmm(debut.theorique.astimezone(self.fuseau))} vers {course.destination} ne dessert pas l'arrêt {self.arrets[course.arrets[i]].nom}.",
                                            "lignes": [ligne.num],
                                            "idCourse": course.id,
                                        })
                elif debut_ts > now_ts:
                    a_venir += 1
                    if prochain_depart is None or debut.prevu < prochain_depart:
                        prochain_depart = debut.prevu
            if not par_ligne.get(ligne.id) or (en_cours == 0 and a_venir == 0):
                etat = 3
            elif restantes and restantes_annulees == restantes and en_cours == 0:
                etat = 6
            elif annulees or arrets_sautes or (retard_max is not None and retard_max >= RETARD_PERTURBATION):
                etat = 5
            elif en_cours == 0:
                etat = 3
            else:
                etat = 1
            infos = infos_par_ligne.get(ligne.num, [])
            infos_en_cours = [i for i in infos if i.get("etat") == "en_cours"]
            infos_a_venir = [i for i in infos if i.get("etat") == "a_venir"]
            candidats = [etat]
            if any(i.get("gravite") == "WARN" for i in infos_en_cours):
                candidats.append(5)
            elif infos_en_cours:
                candidats.append(2)
            if infos_a_venir:
                candidats.append(4)
            etat = max(candidats, key=lambda e: RANG_ETAT.get(e, 0))
            etats.append({
                "infotrafic": [i["id"] for i in infos],
                "infotrafic_en_cours": len(infos_en_cours),
                "infotrafic_a_venir": len(infos_a_venir),
                "idLigne": ligne.id,
                "numLignePublic": ligne.num,
                "nomLigne": ligne.nom,
                "couleurFond": ligne.couleur_fond,
                "couleurTexte": ligne.couleur_texte,
                "etat": etat,
                "courses_jour": len(par_ligne.get(ligne.id, [])),
                "courses_en_cours": en_cours,
                "courses_a_venir": a_venir,
                "courses_annulees": annulees,
                "arrets_non_desservis": arrets_sautes,
                "vehicules_localises": vehicules_par_ligne.get(ligne.id, 0),
                "retard_max": retard_max,
                "prochain_depart": _hhmm(prochain_depart.astimezone(self.fuseau)) if prochain_depart else None,
            })
        return etats, list(infotrafic) + messages

    def _instance_course(self, course: Course, maintenant: datetime) -> datetime:
        meilleure: datetime | None = None
        for jour, base in self.jours_candidats(maintenant):
            if course.id_service not in self.services_actifs(jour):
                continue
            debut = base.timestamp() + course.departs[0] - MARGE_AVANT_COURSE
            fin = base.timestamp() + course.arrivees[-1] + MARGE_APRES_COURSE
            if debut <= maintenant.timestamp() <= fin:
                return base
            meilleure = base
        return meilleure or self.jours_candidats(maintenant)[-1][1]

    def _projeter(self, course: Course, latitude: float, longitude: float) -> tuple[int, int | None, float]:
        points = [(self.arrets[a].latitude, self.arrets[a].longitude) for a in course.arrets]
        plus_proche = min(range(len(points)), key=lambda i: distance_m(latitude, longitude, *points[i]))
        d_proche = distance_m(latitude, longitude, *points[plus_proche])
        if d_proche <= RAYON_A_QUAI:
            return plus_proche, plus_proche, d_proche
        meilleur_seg = 0
        meilleure_d = float("inf")
        lat0 = math.radians(latitude)
        kx = 111320.0 * math.cos(lat0)
        ky = 110540.0
        px, py = longitude * kx, latitude * ky
        for i in range(len(points) - 1):
            ax, ay = points[i][1] * kx, points[i][0] * ky
            bx, by = points[i + 1][1] * kx, points[i + 1][0] * ky
            dx, dy = bx - ax, by - ay
            longueur2 = dx * dx + dy * dy
            t = 0.0 if longueur2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / longueur2))
            cx, cy = ax + t * dx, ay + t * dy
            d = math.hypot(px - cx, py - cy)
            if d < meilleure_d:
                meilleure_d = d
                meilleur_seg = i
        return meilleur_seg + 1, None, meilleure_d

    def positions_ligne(self, id_ligne: str, maintenant: datetime, temps_reel: TempsReel | None) -> list[dict]:
        if temps_reel is None:
            return []
        bus: dict[str, dict] = {}
        now_ts = maintenant.timestamp()
        for v in temps_reel.vehicules:
            course = self.courses.get(v.id_course or "")
            ligne_v = v.id_ligne or (course.id_ligne if course else None)
            if ligne_v != id_ligne:
                continue
            identifiant = v.label or v.id
            entree = {
                "id": identifiant,
                "sens": None,
                "terminus": None,
                "prochain_arret": None,
                "arret_precedent": None,
                "statut": "en_route",
                "dans_sec": None,
                "latitude": v.latitude,
                "longitude": v.longitude,
                "cap": v.cap,
                "age": max(0, int(now_ts - v.horodatage)),
                "gps": True,
                "retard": None,
                "idCourse": v.id_course,
            }
            if course is not None:
                base = self._instance_course(course, maintenant)
                prochain, a_quai, _ = self._projeter(course, v.latitude, v.longitude)
                entree["sens"] = "aller" if course.sens_aller else "retour"
                entree["terminus"] = course.destination
                if a_quai is not None:
                    prediction = self.prediction(course, base, a_quai, temps_reel)
                    entree["prochain_arret"] = self.arrets[course.arrets[a_quai]].nom
                    entree["arret_precedent"] = self.arrets[course.arrets[a_quai - 1]].nom if a_quai > 0 else None
                    entree["statut"] = "depart" if a_quai == 0 and prediction.prevu.timestamp() > now_ts else "a_quai"
                    entree["dans_sec"] = max(0, int(prediction.prevu.timestamp() - now_ts))
                    entree["retard"] = prediction.retard
                else:
                    prochain = min(prochain, len(course.arrets) - 1)
                    prediction = self.prediction(course, base, prochain, temps_reel)
                    entree["prochain_arret"] = self.arrets[course.arrets[prochain]].nom
                    entree["arret_precedent"] = self.arrets[course.arrets[prochain - 1]].nom if prochain > 0 else None
                    entree["dans_sec"] = max(0, int(prediction.prevu.timestamp() - now_ts))
                    entree["retard"] = prediction.retard
            bus[v.id_course or identifiant] = entree
        for id_course, maj in temps_reel.courses.items():
            if id_course in bus:
                continue
            course = self.courses.get(id_course)
            if course is None or course.id_ligne != id_ligne or maj.annulee:
                continue
            if now_ts - maj.horodatage > AGE_MAX_MISE_A_JOUR:
                continue
            base = self._instance_course(course, maintenant)
            if not self._maj_valide(maj, course, base):
                continue
            debut = self.prediction(course, base, 0, temps_reel)
            fin = self.prediction(course, base, len(course.arrets) - 1, temps_reel)
            if not (debut.prevu.timestamp() - 60 <= now_ts <= fin.prevu.timestamp() + 60):
                continue
            idx, prediction = self._prochain_index(course, base, maintenant, temps_reel)
            dans_sec = max(0, int(prediction.prevu.timestamp() - now_ts))
            if idx == 0 and dans_sec > 0:
                statut = "depart"
            elif dans_sec <= 30:
                statut = "a_quai"
            else:
                statut = "en_route"
            bus[id_course] = {
                "id": maj.vehicule or f"course-{id_course}",
                "sens": "aller" if course.sens_aller else "retour",
                "terminus": course.destination,
                "prochain_arret": self.arrets[course.arrets[idx]].nom,
                "arret_precedent": self.arrets[course.arrets[idx - 1]].nom if idx > 0 else None,
                "statut": statut,
                "dans_sec": dans_sec,
                "latitude": None,
                "longitude": None,
                "cap": None,
                "age": max(0, int(now_ts - maj.horodatage)),
                "gps": False,
                "retard": prediction.retard,
                "idCourse": id_course,
            }
        resultat = list(bus.values())
        resultat.sort(key=lambda b: (b["dans_sec"] is None, b["dans_sec"] or 0))
        return resultat
