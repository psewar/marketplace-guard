# Marketplace Guard

Security checks for custom components from Home Assistant's Marketplace, HACS or installed by hand: automatic
quarantine of risky new components, repository pre-checks before you install, and an optional AI second opinion.

Home Assistant offers no hook before a download and no built-in way to check custom integrations for security problems.
Marketplace Guard closes that gap without changing the Marketplace or HACS. Until version 2.0.0 it was called
*HACS Guard* (bis Version 2.0.0 hieß es *HACS Guard*).

---

## English

### What it does
- **Checks every new or changed component.** It watches `custom_components` and the frontend folder. A component
  that reaches the quarantine threshold (default `high`) is moved to a quarantine folder (never deleted), so Home
  Assistant does not load it. Everything installed before the first start is recorded as trusted and only reported.
- **Pre-checks a repository before you install it.** Run the action `hassio.addon_stdin` with `owner/repo` (or write
  it into a text file) and get a verdict as a notification; nothing is installed.
- **Optional AI second opinion.** An AI Task of your choice judges the code in addition; it can only make a verdict
  stricter.

It runs `pip-audit` (known vulnerabilities of pinned dependencies), `bandit` (Python static analysis), its own checks
(secret access, shell and `exec`, runtime downloads, hidden Unicode, compiled code) and checks the lists of critical
and removed repositories.

### Getting started
1. Install and start the app. The defaults work as they are. Turn on **Show in sidebar** for its web page: status,
   pre-checks, the components in quarantine with their reports, and restoring one.
2. After the first scan one notification sums up what was recorded, what is worth a look and what you can set next;
   later you get one only when something needs your attention. The sensor `sensor.marketplace_guard` shows how many
   components are in quarantine.
3. Optional, on the **Configuration** tab: a push target for your phone (`mobile_app_<device>`), and the AI second
   opinion.

The **Documentation** tab explains everyday use (pre-checks, reports, restoring a component), every option, and the
limits of static analysis.

---

## Deutsch

### Was es tut
- **Prüft jede neue oder geänderte Komponente.** Es überwacht `custom_components` und den Frontend-Ordner. Eine
  Komponente, die die Quarantäne-Schwelle erreicht (Standard `high`), wird in einen Quarantäne-Ordner verschoben (nie
  gelöscht), damit Home Assistant sie nicht lädt. Alles, was vor dem ersten Start installiert war, gilt als vertraut
  und wird nur gemeldet.
- **Prüft ein Repository vor der Installation.** Die Aktion `hassio.addon_stdin` mit `owner/repo` ausführen (oder es in
  eine Textdatei schreiben) und das Urteil als Benachrichtigung erhalten; installiert wird nichts.
- **Optionale KI-Zweitmeinung.** Eine AI-Task deiner Wahl beurteilt den Code zusätzlich; sie kann ein Urteil nur
  verschärfen.

Es nutzt `pip-audit` (bekannte Schwachstellen festgelegter Abhängigkeiten), `bandit` (statische Python-Analyse),
eigene Prüfungen (Secret-Zugriff, Shell und `exec`, Laufzeit-Downloads, verstecktes Unicode, kompilierter Code) und die
Listen kritischer und entfernter Repositories.

### Erste Schritte
1. App installieren und starten. Die Standardwerte funktionieren so. **In der Seitenleiste anzeigen** einschalten für
   ihre Webseite: Status, Vorprüfungen, die Komponenten in Quarantäne mit ihren Berichten, und eine wiederherstellen.
2. Nach dem ersten Scan fasst eine Benachrichtigung zusammen, was aufgenommen wurde, was einen Blick wert ist und was du
   als Nächstes einstellen kannst; danach kommt eine nur, wenn etwas deine Aufmerksamkeit braucht. Der Sensor
   `sensor.marketplace_guard` zeigt, wie viele Komponenten in Quarantäne sind.
3. Optional im Tab **Konfiguration**: ein Push-Ziel für dein Handy (`mobile_app_<gerät>`) und die KI-Zweitmeinung.

Der Tab **Dokumentation** erklärt die tägliche Nutzung (Vorprüfung, Berichte, Komponente wiederherstellen), jede
Option und die Grenzen statischer Analyse.
