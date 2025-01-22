#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "arrow",
#     "ics",
# ]
# [tool.uv]
# exclude-newer = "2026-12-11T00:00:00Z"
# ///

import sys
import locale
from dateutil import tz
import csv
from datetime import datetime, timedelta
from pathlib import Path

import arrow
from ics import Calendar, Event, Geo, DisplayAlarm
from ics.grammar.parse import ContentLine
from ics.alarm import EmailAlarm
from ics.attendee import Organizer, Person


PARCOURS_FICHIER = Path(__file__).parent / "datas" / "parcours.2009.2025.csv"  # no;km;parcours
CALENDRIER_FICHIER = Path(__file__).parent / "datas" / "2025.calendrier.velo.csv"  # date;grand;moyen;petit;mois
GPS_FICHIER = Path(__file__).parent / "datas" / "openrunner.csv"

tz_str = "Europe/Paris"
TZ_PARIS = tz.gettz(tz_str)
locale.setlocale(locale.LC_TIME, "")

gps = {}
with open(GPS_FICHIER, "r") as fp:
    reader = csv.reader(fp, delimiter=";")
    for row in reader:
        gps[str(row[0])] = row[1]

parcours = {}
with open(PARCOURS_FICHIER, "r") as fp:
    reader = csv.DictReader(fp, delimiter=";")
    for row in reader:
        row["gps"] = gps.get(row["no"], "")
        parcours[row["no"]] = row


date_filtre = datetime(2000, 1, 1)
if len(sys.argv) > 1:  # and sys.argv[1].lower() == 'now':
    dt = datetime.now()
    date_filtre = datetime(dt.year, dt.month, dt.day)

cal_name = f"OCM Cyclo {' '.join(sys.argv[1:]).replace('--', '').strip()}"

calendar = Calendar(creator="OCM//fr")
calendar.extra.append(ContentLine(name="X-WR-CALNAME", value=cal_name))
calendar.extra.append(ContentLine(name="NAME", value=cal_name))
calendar.extra.append(ContentLine(name="X-WR-CALDESC", value=f"Calendier des sorties classiques 2025 {cal_name}"))
calendar.extra.append(ContentLine(name="LOCATION", value="Montauban-de-Bretagne, 35360 Montauban-de-Bretagne, France"))


calendar.extra.append(ContentLine(name="X-WR-TIMEZONE", value=tz_str))
calendar.extra.append(ContentLine(name="METHOD", value="PUBLISH"))
"""
calendar.extra.append(ContentLine(
    name="X-WR-TIMEZONE",
    value="UTC"
))"""


"""
TODO
    arg: --now
    Un seul calendrier par jour ...
    args:
        --mercredi
        --samedi
        --dimanche
    ou possible de coupler:
        --mercredi --samedi
    # si pas dans ces 3 jours ? ajouter quand même ?
"""

DAYS = ("mercredi", "samedi", "dimanche")


def day_in_filter(day: str) -> bool:
    """jour est autre que les 3 valides OU est dans un argument du script"""
    day = day.lower()
    if day not in DAYS:
        return True
    if f"--{day.lower()}" in sys.argv[1:]:
        return True
    return False


"""
# Pas utilisé : google cal n'importe pas les Alarmes !
alarm = DisplayAlarm(trigger=timedelta(hours=-2), display_text='This is an event reminder')
"""


# DisplayAlarm(trigger=timedelta(hours=-72)),
# EmailAlarm(trigger=timedelta(hours=-72), subject='Alarm notification'),

i = 0


with open(CALENDRIER_FICHIER, "r") as fp:
    reader = csv.DictReader(fp, delimiter=";")
    for row in reader:
        dt = datetime.strptime(row["date"] + " 14", "%Y-%m-%d %H")
        if dt < date_filtre:
            continue
        try:
            parcour = parcours[row["grand"]]
            if not str(parcour["km"]).endswith("km"):
                parcour["km"] = parcour["km"] + " km"
        except KeyError:
            parcour = {"km": "?   ", "parcours": "?"}
        jour = f"{dt:%A}"

        if not day_in_filter(jour):
            continue

        i += 1
        if i > 50000:  # TEST passe 5
            continue

        event = Event()
        # event.organizer = Organizer(None, 'moi')
        event.name = f"OCM Cyclo: {row['grand']} - {parcour['km']:>6}"
        desc = ""
        for duree in ("grand", "moyen", "petit"):
            parcour_id = row[duree]
            try:
                parc = parcours[parcour_id]
                if not str(parc["km"]).endswith("km"):
                    parc["km"] = parc["km"] + " km"
            except KeyError:
                # 821, 822, 823  le 2023-06-07
                parc = {"km": "?   ", "parcours": "?", "gps": ""}
            gps = ""
            if parc.get("gps", ""):
                gps = f"\nhttps://www.openrunner.com/route-details/{parc.get('gps', '')}"
                event.url = gps[1:]
            desc = f"{desc}<em>{parcour_id}</em> - {parc['km']:>8} ({duree})\n\n{parc['parcours']}{gps}<hr>\n"
        event.description = desc  # f"{row['grand']} - {parcour['km']:>6} (grand)\n\n{parcour['parcours']}"
        # FIXED decalage heure ?
        event.begin = dt.replace(hour=14, tzinfo=TZ_PARIS)
        if jour == "dimanche":
            event.begin = dt.replace(hour=9, tzinfo=TZ_PARIS)
        event.duration = dict({"hours": 2, "minutes": 30})
        event.location = "Montauban-de-Bretagne, 35360 Montauban-de-Bretagne, France"
        event.geo = Geo(48.19876, -2.0565)  # used https://www.coordonnees-gps.fr/

        # event.alarms = [alarm]

        calendar.events.add(event)


calendar.events = sorted(calendar.events, key=lambda x: x.begin, reverse=False)

fichier = Path(__file__).parent / f"ocm-cyclo.{' '.join(sys.argv[1:]).replace('--', '').strip()}.ics"
with open(fichier, "w") as f:
    f.writelines(calendar.serialize_iter())

print(calendar)
print()
print("#", len(calendar.events), "sorties")
print("# Sauvegardé dans:", fichier)
