"""Dataset-free demo wiring: tiny hand-written KB, hashing encoder, small TF-IDF classifier.

Needs no Hugging Face dataset, no model download and no artifacts/ folder. It exists to show the
pipeline, gate and UI end to end while the real classifier and retriever are built.
The real components plug into SentinelDesk(classifier=..., retriever=...) with the same interface.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer

from .classifier import TriageClassifier
from .config import SETTINGS
from .data import TARGETS, build_text
from .generator import Generator
from .pipeline import SentinelDesk
from .retriever import Retriever

# (subject, body, answer, type, queue, priority, language)
_TOPICS = {
    "vpn": [
        ("VPN down", "VPN outage: nobody can connect to the VPN gateway, all users are offline.",
         "Restart the VPN gateway service and renew the expired certificate. Confirm tunnels re-establish.",
         "Incident", "Technical Support", "high", "en"),
        ("VPN ausgefallen", "Die VPN-Verbindung ist komplett ausgefallen, kein Benutzer kann sich verbinden.",
         "VPN-Gateway neu starten und das abgelaufene Zertifikat erneuern. Danach die Tunnel prüfen.",
         "Incident", "Technical Support", "high", "de"),
        (None, "VPN gateway not reachable, remote staff cannot connect since this morning.",
         "Restart the VPN gateway service and check the firewall rule for UDP 1194.",
         "Incident", "Technical Support", "high", "en"),
        ("VPN Störung", "Seit heute früh keine VPN Verbindung möglich, Mitarbeiter im Homeoffice betroffen.",
         "Firewallregel für UDP 1194 prüfen und den VPN-Dienst neu starten.",
         "Incident", "Technical Support", "high", "de"),
    ],
    "password": [
        ("Password reset", "I forgot my password and cannot log in to the portal.",
         "Use the 'Forgot password' link on the login page. A reset mail arrives within a few minutes.",
         "Request", "IT Support", "low", "en"),
        ("Passwort vergessen", "Ich habe mein Passwort vergessen und kann mich nicht im Portal anmelden.",
         "Nutzen Sie den Link 'Passwort vergessen' auf der Anmeldeseite. Die E-Mail kommt in wenigen Minuten.",
         "Request", "IT Support", "low", "de"),
        (None, "Please reset my password, my account is locked after too many attempts.",
         "Account entsperren wurde durchgeführt. Use the 'Forgot password' link to set a new password.",
         "Request", "IT Support", "low", "en"),
        ("Konto gesperrt", "Mein Konto ist gesperrt, bitte Passwort zurücksetzen.",
         "Das Konto wurde entsperrt. Bitte setzen Sie über 'Passwort vergessen' ein neues Passwort.",
         "Request", "IT Support", "low", "de"),
    ],
    "invoice": [
        ("Invoice question", "The amount on my latest invoice looks wrong, please check it.",
         "We reviewed the invoice and sent a corrected copy to your billing contact.",
         "Problem", "Billing and Payments", "medium", "en"),
        ("Rechnung falsch", "Der Betrag auf meiner Rechnung stimmt nicht, bitte prüfen.",
         "Wir haben die Rechnung geprüft und eine korrigierte Kopie an Ihren Rechnungskontakt gesendet.",
         "Problem", "Billing and Payments", "medium", "de"),
        (None, "Invoice shows a duplicate charge for the same month.",
         "The duplicate position was removed and a corrected invoice was issued.",
         "Problem", "Billing and Payments", "medium", "en"),
        ("Doppelte Abbuchung", "Auf der Rechnung ist ein Monat doppelt berechnet worden.",
         "Die doppelte Position wurde entfernt und eine korrigierte Rechnung ausgestellt.",
         "Problem", "Billing and Payments", "medium", "de"),
    ],
    "sales": [
        ("Product question", "Does the product support single sign-on and how do I get a demo?",
         "Single sign-on is described in the product documentation. A demo can be booked via the sales page.",
         "Request", "Sales and Pre-Sales", "low", "en"),
        ("Frage zum Produkt", "Unterstützt das Produkt Single Sign-on und wie bekomme ich eine Demo?",
         "Single Sign-on ist in der Produktdokumentation beschrieben. Eine Demo können Sie über die Vertriebsseite buchen.",
         "Request", "Sales and Pre-Sales", "low", "de"),
        (None, "I would like a product demo and information about available plans.",
         "A demo can be booked via the sales page. Plan details are listed in the product documentation.",
         "Request", "Sales and Pre-Sales", "low", "en"),
        ("Demo anfragen", "Ich möchte eine Produktdemo und Informationen zu den verfügbaren Tarifen.",
         "Eine Demo können Sie über die Vertriebsseite buchen. Tarifdetails stehen in der Produktdokumentation.",
         "Request", "Sales and Pre-Sales", "low", "de"),
    ],
    "access": [
        ("Access change", "Please add me to the finance shared folder, my role changed.",
         "Access to the finance folder was granted after manager approval. Sign out and in again.",
         "Change", "IT Support", "medium", "en"),
        ("Zugriff ändern", "Bitte fügen Sie mich zum Finanzordner hinzu, meine Rolle hat sich geändert.",
         "Der Zugriff auf den Finanzordner wurde nach Freigabe des Vorgesetzten erteilt. Bitte neu anmelden.",
         "Change", "IT Support", "medium", "de"),
        (None, "Need permission to edit the shared project folder for my new team.",
         "Edit permission was granted after manager approval. Sign out and in again.",
         "Change", "IT Support", "medium", "en"),
        ("Berechtigung", "Ich brauche Schreibrechte für den Projektordner meines neuen Teams.",
         "Schreibrechte wurden nach Freigabe des Vorgesetzten erteilt. Bitte neu anmelden.",
         "Change", "IT Support", "medium", "de"),
    ],
    "mail": [
        ("Email sync", "My mailbox does not sync on the phone since the update.",
         "Remove and re-add the mail account on the phone, then wait for the full resync.",
         "Problem", "Technical Support", "medium", "en"),
        ("E-Mail Synchronisation", "Mein Postfach synchronisiert seit dem Update nicht mehr auf dem Handy.",
         "Konto auf dem Handy entfernen und neu hinzufügen, danach die vollständige Synchronisation abwarten.",
         "Problem", "Technical Support", "medium", "de"),
        (None, "Calendar and mail are not updating on my phone.",
         "Remove and re-add the account on the phone, then wait for the resync to finish.",
         "Problem", "Technical Support", "medium", "en"),
        ("Kalender aktualisiert nicht", "Kalender und E-Mails werden auf meinem Handy nicht aktualisiert.",
         "Konto entfernen und neu hinzufügen, anschließend die Synchronisation abwarten.",
         "Problem", "Technical Support", "medium", "de"),
    ],
}


class HashEncoder:
    """Offline stand-in for multilingual-e5-small (lexical, not cross-lingual)."""

    model_name = "hashing-demo"

    def __init__(self):
        self.v = HashingVectorizer(n_features=1024, alternate_sign=False, norm="l2", ngram_range=(1, 2))

    def encode(self, texts, **_):
        return self.v.transform(texts).toarray().astype("float32")


def demo_kb() -> pd.DataFrame:
    cols = ["subject", "body", "answer", "type", "queue", "priority", "language"]
    rows = [r for topic in _TOPICS.values() for r in topic]
    df = pd.DataFrame(rows, columns=cols)
    df["ticket_id"] = [f"DEMO-{i:03d}" for i in range(len(df))]
    df["text"] = [build_text(s, b) for s, b in zip(df["subject"], df["body"])]
    return df


def build_demo_desk() -> SentinelDesk:
    kb = demo_kb()
    clf = TriageClassifier().fit(kb["text"].tolist(), {t: kb[t].tolist() for t in TARGETS}, verbose=False)
    retriever = Retriever(HashEncoder()).build(kb, show_progress=False)
    # Point at a folder that does not exist so tuned thresholds from real artifacts are not picked up.
    settings = dataclasses.replace(SETTINGS, artifacts_dir=Path("artifacts") / "_demo_unused")
    desk = SentinelDesk(settings, classifier=clf, retriever=retriever, generator=Generator("none"))
    desk.sim_threshold, desk.risk_threshold = 0.25, 0.22  # hashing similarities are lower than e5
    return desk
