from __future__ import annotations

from google.transit import gtfs_realtime_pb2

from .const import AGE_MAX_POSITION
from .gtfs import ArretMaj, MiseAJourCourse, PositionVehicule, TempsReel

_TRIP_CANCELED = gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.Value("CANCELED")
_STOP_SKIPPED = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.ScheduleRelationship.Value("SKIPPED")


def _lire(contenu: bytes) -> gtfs_realtime_pb2.FeedMessage:
    message = gtfs_realtime_pb2.FeedMessage()
    message.ParseFromString(contenu)
    return message


def analyser_mises_a_jour(contenu: bytes, resultat: TempsReel) -> None:
    flux = _lire(contenu)
    horodatage_flux = int(flux.header.timestamp) if flux.header.HasField("timestamp") else resultat.horodatage
    if horodatage_flux and horodatage_flux > resultat.horodatage:
        resultat.horodatage = horodatage_flux
    for entite in flux.entity:
        if not entite.HasField("trip_update"):
            continue
        tu = entite.trip_update
        id_course = tu.trip.trip_id
        if not id_course:
            continue
        if tu.HasField("timestamp") and int(tu.timestamp) > resultat.derniere_donnee:
            resultat.derniere_donnee = int(tu.timestamp)
        maj = MiseAJourCourse(
            id_course=id_course,
            id_ligne=tu.trip.route_id,
            date_debut=tu.trip.start_date,
            horodatage=int(tu.timestamp) if tu.HasField("timestamp") else horodatage_flux,
            annulee=tu.trip.schedule_relationship == _TRIP_CANCELED,
            vehicule=(tu.vehicle.label or tu.vehicle.id or None) if tu.HasField("vehicle") else None,
            retard_course=int(tu.delay) if tu.HasField("delay") else None,
        )
        for stu in tu.stop_time_update:
            evenement = stu.arrival if stu.HasField("arrival") else stu.departure if stu.HasField("departure") else None
            arret_maj = ArretMaj(
                sequence=int(stu.stop_sequence) if stu.HasField("stop_sequence") else None,
                id_arret=stu.stop_id or None,
                retard=int(evenement.delay) if evenement is not None and evenement.HasField("delay") else None,
                heure=int(evenement.time) if evenement is not None and evenement.HasField("time") else None,
                saute=stu.schedule_relationship == _STOP_SKIPPED,
            )
            if arret_maj.sequence is not None:
                maj.par_sequence[arret_maj.sequence] = arret_maj
            if arret_maj.id_arret:
                maj.par_arret.setdefault(arret_maj.id_arret, arret_maj)
        resultat.courses[id_course] = maj


def analyser_positions(contenu: bytes, resultat: TempsReel, maintenant_ts: float) -> None:
    flux = _lire(contenu)
    horodatage_flux = int(flux.header.timestamp) if flux.header.HasField("timestamp") else 0
    if horodatage_flux > resultat.horodatage:
        resultat.horodatage = horodatage_flux
    for entite in flux.entity:
        if not entite.HasField("vehicle"):
            continue
        vp = entite.vehicle
        if not vp.HasField("position"):
            continue
        horodatage = int(vp.timestamp) if vp.HasField("timestamp") else horodatage_flux
        if vp.HasField("timestamp") and horodatage > resultat.derniere_donnee:
            resultat.derniere_donnee = horodatage
        if not horodatage or maintenant_ts - horodatage > AGE_MAX_POSITION:
            continue
        identifiant = vp.vehicle.id or vp.vehicle.label or entite.id
        resultat.vehicules.append(PositionVehicule(
            id=identifiant,
            label=vp.vehicle.label or None,
            id_course=vp.trip.trip_id or None,
            id_ligne=vp.trip.route_id or None,
            latitude=float(vp.position.latitude),
            longitude=float(vp.position.longitude),
            cap=float(vp.position.bearing) if vp.position.HasField("bearing") else None,
            horodatage=horodatage,
        ))


def construire_temps_reel(mises_a_jour: bytes | None, positions: bytes | None, maintenant_ts: float) -> TempsReel:
    resultat = TempsReel()
    if mises_a_jour:
        analyser_mises_a_jour(mises_a_jour, resultat)
        resultat.disponible = True
    if positions:
        analyser_positions(positions, resultat, maintenant_ts)
        resultat.disponible = True
    return resultat
