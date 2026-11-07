# Marketplace Guard

Security scanning for Home Assistant's Marketplace, HACS and `custom_components` — automatic quarantine of newly
installed components, on-demand repository pre-checks, and an optional AI second opinion.

Home Assistant offers no pre-download hook and no built-in way to check installed custom integrations
for security issues. Marketplace Guard closes that gap without modifying the Marketplace or HACS.
Until version 2.0.0 it was called *HACS Guard* (Bis Version 2.0.0 hiess es *HACS Guard*).

---

## English

### Features
- **Automatic quarantine on install** — watches the custom-component and frontend folders; new or
  changed components are scanned and, if risky, moved aside (never deleted) before Home Assistant can
  load them. Already-installed components are trusted on first start (baseline) and never quarantined.
  Since Home Assistant 2026.11 the Marketplace sets a new integration up without a restart, so it may
  run before the scan: the notification says so, and risky updates can be quarantined before they load.
- **Repository pre-check** — write a GitHub URL into the request file and get a verdict before you
  install the repository from HACS or the Marketplace.
- **AI second opinion (optional, off by default)** — a Home Assistant AI Task of your choice adds an
  independent judgement. With a local model the code stays on your network.

### Scan layers
`pip-audit` (CVEs of exactly pinned dependencies) · `bandit` (Python static analysis) · custom heuristics
(secret access, shell/exec, runtime downloads, decode-and-execute, raw-IP URLs, hidden Unicode such as
Trojan Source) · critical and removed repositories · the optional AI review.

### Install
1. Settings → Add-ons → Add-on Store → ⋮ → **Repositories**, add the URL of this repository.
2. Install **Marketplace Guard** and start it. The defaults work as they are: alerts appear as notifications in
   Home Assistant, and everything installed before the first start is trusted (baseline).
3. Optional: on the **Configuration** tab add push targets or turn on the AI second opinion (every
   option is documented there).

As a local add-on instead: copy the `marketplace_guard` folder to `/addons/marketplace_guard/`, then Add-on Store →
⋮ → *Check for updates* and install it from *Local add-ons*.

### Usage
- Reports are written to `/homeassistant/marketplace_guard/reports/`; alerts arrive as notifications.
- To pre-check a repository: put a GitHub URL (one per line) in
  `/homeassistant/marketplace_guard/scan_request.txt`.
- To restore a quarantined component: add it to the allowlist, move its folder from
  `/homeassistant/_marketplace_quarantine/` back to `custom_components/` and restart Home Assistant.

### Limitations
Static analysis catches known-vulnerable dependencies and suspicious patterns — it is not a malware
guarantee. Minified frontend JavaScript is barely analysable statically (heuristics are informational).
Use Marketplace Guard as a strong filter and tripwire, alongside good repository hygiene.

---

## Deutsch

### Funktionen
- **Automatische Quarantäne bei Installation** — überwacht die custom_components- und Frontend-Ordner;
  neue/geänderte Komponenten werden gescannt und bei Risiko beiseite geschoben (nie gelöscht), bevor
  Home Assistant sie laden kann. Bereits installierte Komponenten gelten beim ersten Start als
  vertraut (Baseline) und werden nie quarantäniert. Seit Home Assistant 2026.11 richtet der Marketplace
  eine neue Integration ohne Neustart ein, sie kann also vor dem Scan laufen: die Benachrichtigung sagt
  das, und riskante Updates lassen sich quarantänieren, bevor sie geladen werden.
- **Repository-Vorprüfung** — eine GitHub-URL in die Anforderungsdatei schreiben und ein Urteil
  erhalten, bevor du das Repo aus HACS oder dem Marketplace installierst.
- **KI-Zweitmeinung (optional, standardmäßig aus)** — eine Home-Assistant-AI-Task deiner Wahl liefert
  ein unabhängiges Urteil. Mit einem lokalen Modell bleibt der Code im eigenen Netz.

### Scan-Ebenen
`pip-audit` (CVEs genau festgelegter Abhängigkeiten) · `bandit` (statische Python-Analyse) · eigene
Heuristik (Secret-Zugriff, Shell/Exec, Laufzeit-Downloads, Decode-und-Ausführen, Roh-IP-URLs, verstecktes
Unicode wie Trojan Source) · kritische und entfernte Repositories · die optionale KI-Prüfung.

### Installation
1. Einstellungen → Add-ons → Add-on-Store → ⋮ → **Repositories**, die URL dieses Repositorys hinzufügen.
2. **Marketplace Guard** installieren und starten. Die Standardwerte funktionieren so: Meldungen erscheinen als
   Benachrichtigung in Home Assistant, und alles, was vor dem ersten Start installiert war, gilt als
   vertraut (Baseline).
3. Optional: im **Konfiguration**-Tab Push-Ziele eintragen oder die KI-Zweitmeinung einschalten (jede
   Option ist dort beschrieben).

Stattdessen als lokales Add-on: den Ordner `marketplace_guard` nach `/addons/marketplace_guard/` kopieren, dann
Add-on-Store → ⋮ → *Nach Updates suchen* und unter *Lokale Add-ons* installieren.

### Bedienung
- Reports liegen unter `/homeassistant/marketplace_guard/reports/`; Warnungen kommen als Benachrichtigung.
- Repo vorprüfen: GitHub-URL (eine pro Zeile) in `/homeassistant/marketplace_guard/scan_request.txt` schreiben.
- Quarantänierte Komponente wiederherstellen: in die Allowlist eintragen, Ordner aus
  `/homeassistant/_marketplace_quarantine/` zurück nach `custom_components/` verschieben und Home Assistant neu
  starten.

### Grenzen
Statische Analyse erkennt bekannte verwundbare Abhängigkeiten und verdächtige Muster — keine
Malware-Garantie. Minifiziertes Frontend-JavaScript ist statisch kaum bewertbar (Heuristik nur
informativ). Verstehe Marketplace Guard als starken Filter und Stolperdraht, ergänzt durch gute Repo-Hygiene.

---

## Add-on structure
`config.yaml` (add-on manifest) · `build.yaml` (Debian base image) · `Dockerfile` · `run.sh` (entry,
`with-contenv` for `SUPERVISOR_TOKEN`) · `scanner.py` (scan logic) · `guard.py` (daemon, notifications,
quarantine, repository pre-check, AI review) · `translations/` (localized configuration texts) ·
`DOCS.md` (documentation shown in Home Assistant).
