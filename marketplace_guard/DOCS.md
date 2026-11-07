# Marketplace Guard

A security tripwire for Home Assistant's Marketplace, HACS and `custom_components`. Home Assistant offers no
pre-download hook and no built-in way to check installed custom integrations for security problems — Marketplace
Guard fills that gap with three complementary layers and an optional AI second opinion. Until version 2.0.0 the
add-on was called *HACS Guard*.

---

## English

### What it does

**1. Automatic quarantine on install**
A watcher monitors your custom-component and frontend-plugin folders. Whenever a component is newly
installed or changed, it is scanned. If the verdict reaches the configured threshold (default `high`),
the component is **moved** to a quarantine folder (never deleted) **before** the next Home Assistant
restart can load it. The key idea: downloading a component is not the same as executing it — custom
integrations only run when Home Assistant loads them, and that window is the gate.

> **Baseline protection:** on the very first start, all already-installed components are recorded as
> *trusted* and are never quarantined — only reported. Only components installed or changed afterwards
> are eligible for quarantine, so a running system is never disrupted. A component Marketplace Guard finds at a
> later start without having seen it before (installed while the add-on was stopped) counts as newly
> installed. If the saved state cannot be read, the baseline is recorded again and a notification says so.

> **Home Assistant 2026.11 and later (Marketplace):** HACS is now built into Home Assistant as the
> Marketplace, and it sets up a new integration right after the download, **without a restart**. HACS
> Guard still finds and quarantines it within seconds, but its code may already have run: pre-check a
> repository *before* you install it (layer 2). After quarantining a new integration, the notification
> says whether it is running in Home Assistant; **Restart after quarantining a running integration**
> restarts Home Assistant for you. Updates still need a restart, so **Quarantine risky updates** (on by
> default) stops an update that brings a new risk before it loads. Marketplace Guard reads the Marketplace's records, and those
> of HACS on older versions of Home Assistant.

**2. Repository pre-check (before you download)**
Write one or more GitHub URLs into the request file (`/homeassistant/marketplace_guard/scan_request.txt`; the
add-on creates it with instructions on its first start). Each repository is downloaded to a temporary
folder, scanned (it is **not** installed) and reported — so you can vet a repository *before* installing
it from HACS or the Marketplace. It scans what they would install: the newest release (the default branch
if there is none) and the integration folder they pick; the report says which. If they install a release asset
(`zip_release`), the report says that this asset was not scanned — the installed files are scanned on
install anyway.

**3. AI second opinion (optional, off by default)**
After the static scan, a Home Assistant AI Task can additionally judge the component. It is a third,
independent voter that *complements* the static scan and never weakens it.

### Scan layers
- **pip-audit** — checks the `manifest.json` requirements that are pinned to an exact version
  (`name==1.2.3`) against the known-vulnerability (CVE) database; a known vulnerability is rated `high`.
  Nothing is installed for this: only name and version are looked up. Requirements given as a range or
  without a version are listed as not audited.
- **bandit** — static analysis of the Python code (shell/exec, pickle, weak crypto, …). It runs with Marketplace
  Guard's own settings: a component cannot switch checks off (`# nosec`, `.bandit` files).
- **Heuristics** — access to the HA secret store / `secrets.yaml`, `eval`/`exec`, shell execution,
  runtime downloads, decode-and-execute patterns, raw-IP URLs. Outbound vendor hosts are *informational
  only* and never raise the verdict. Python is read the way Python reads it: its tokenizer finds the
  comments and the docstrings, which are text, not code (unless a file of the component reads docstrings,
  `__doc__`: then they are scanned as code), and a source encoding that can hide code (such as UTF-7) is
  rated `high`.
- **What is loaded** — `.mjs`/`.cjs` scripts and the compressed copies (`.js.gz`, `.js.br`) the web server
  sends instead of a script are checked: a copy that differs from its script, or one that cannot be
  reviewed, is rated `high`. Symbolic links leaving a component and special files are rated `high` and
  never read. Files are scanned up to 16 MiB. A larger Python file is read whole by Python's tokenizer:
  if it holds only data (constants such as embedded images) it is informational, otherwise it is rated
  `high`. bandit analyses Python files up to 2 MiB; a larger one is reported (code of real integrations
  stays far below both limits).
- **Compiled code** — native modules (`.so`, `.pyd`), bytecode without source, and bytecode marked to run
  without checking its source are rated `high`: Python would run code nobody can review.
- **Hidden Unicode** — bidirectional control characters (Trojan Source) in Python, JavaScript and JSON
  files, comments included, are rated `high`: the code would display in another order than it runs.
  Invisible characters (zero width) next to ordinary text are `medium` in Python and informational in
  JavaScript; emoji, Persian or Indic text and translations are not affected.
- **Critical and removed repositories** — Home Assistant's own list of critical repositories and the
  catalog's lists of critical and removed repositories (read every six hours) are rated `critical`. If a
  list cannot be read, the report says so.
- **AI second opinion** — see above.

### Verdicts and thresholds
Findings are rated `info` < `low` < `medium` < `high` < `critical`. A component is **quarantined** when
its highest finding reaches **Quarantine threshold** (default `high`); below that, it only triggers a
**notification** if it reaches **Notification threshold** (default `medium`). Reports for every scan are
written to `/homeassistant/marketplace_guard/reports/`. In notifications, text that comes from a component (names,
hosts, requirements, the AI's reason) is shown as code, so it is never a link or formatting.

### Restoring a quarantined component
Quarantine only *moves* a component to `…/_marketplace_quarantine/<name>__<timestamp>/` (with a
`SCAN_REPORT.txt`). If you trust it (for example a well-known power tool), first add its folder name or
repository to **Allowlist**, then move the folder back to `custom_components/` and restart Home Assistant.
Without the allowlist entry, a quarantined component that appears again — moved back, or downloaded again
by HACS — counts as a new install and is quarantined again.

### AI second opinion & privacy
The AI review is **off by default**; turn on **AI second opinion** to use it. It needs an AI Task
integration in Home Assistant (a local model, e.g. through Ollama, or a cloud service). Leave **AI Task**
empty to use the AI Task entity Home Assistant prefers, or enter an entity id. The add-on log and the
status sensor's `ai_task_entities` attribute list the AI Task entities your Home Assistant has, and the
`ai_review` attribute says whether the review is ready. **Privacy:** the component's (public) source code
and the scan findings go to the model behind the AI Task; with a cloud service they leave your network.

By default the AI cannot quarantine on its own (`Let AI trigger quarantine` is off): a malicious AI
verdict is only reported, because small local models can produce false positives. A component whose static
verdict already reaches the quarantine threshold is quarantined at once, without waiting for the AI; the
AI can only raise a verdict, never lower it. You can steer what the
AI focuses on in `ai_prompt.txt` in the add-on's configuration folder (`addon_configs/<...>_marketplace_guard/`,
reached through the Samba, File editor or SSH add-on; created with examples on the first start; free text,
appended to the security prompt on every scan). Home Assistant integrations cannot write that folder. A file
`ai_prompt.txt` next to the request file (`/homeassistant/marketplace_guard/`) is not read; if it holds
instructions, a notification asks you to move them. The full AI assessment is saved in the
per-component report. The AI sees the lines around the static findings first, then the rest of the code
up to **AI source limit**; for a dashboard card, the start of its scripts. Everything taken from the
component is marked as untrusted data, and only the first line of the answer counts: an answer that does
not start with the `VERDICT=` line is reported as unusable instead of being guessed from.

If Home Assistant or the AI Task cannot be reached during a review (for example while Home Assistant
restarts, or while the model is not running), the component is handled on its static verdict first and
the review is tried again: after 15 minutes, 1, 4 and 12 hours, then it is given up (see the log). The
status sensor's `ai_review_pending` attribute lists the components waiting. A verdict reached on a retry
counts as it would have at the scan, so a new component can still be quarantined. A missing AI Task
entity or a turned-off review is not retried; the log says what to set.

### Honest limitations
Static analysis catches known-vulnerable dependencies and suspicious patterns; it is **not** a malware
guarantee — a determined author can evade it. Minified frontend bundles are barely analysable statically,
so JavaScript heuristics are informational only. The dependency check sees only the requirements a
component pins to an exact version, not the packages those depend on, and needs a connection to PyPI
(without one, the report says which requirements were not audited). Since Home Assistant 2026.11 a new
integration can run before Marketplace Guard has scanned it (see above); the pre-check is the way to look first.
Treat Marketplace Guard as a strong filter
and tripwire, not a certificate of safety. Keeping to few, popular, actively-maintained repositories
remains the foundation.

### Configuration
All options are documented inline on the **Configuration** tab, and the defaults work without changes:
alerts appear as persistent notifications in Home Assistant. Options you may want to change: 
**Notification targets** (add a notify service such as `mobile_app_<device>` for push messages) and
**AI second opinion**, and for the Marketplace **Quarantine risky updates** (on by default: an update that
brings a risk the version before did not have is quarantined, and the integration is then missing after
the next restart until you install a version you trust; turn it off to be only notified) and **Restart
after quarantining a running integration**. A
notification target Home Assistant does not have is skipped and named in the
log (and in the status sensor's `notify_problems` attribute); if none is usable, alerts fall back to a
persistent notification.

The log names the runtime at the start, and the status sensor carries it: `python_version`,
`tar_data_filter` (whether Python has the `data` filter used to unpack downloaded repositories),
`bandit_version` and `pip_audit_version` (`missing` when the tool is not installed), and which code runs:
`code_source` (`built-in`, or `override` for code in `code/` of the add-on's configuration folder) and
`code_sha256`.

---

## Deutsch

Bis Version 2.0.0 hiess das Add-on *HACS Guard*; es trägt jetzt den Namen, den Home Assistant seit 2026.11 für den
Installationsweg verwendet.

### Was es tut

**1. Automatische Quarantäne bei Installation**
Ein Watcher überwacht deine custom_components- und Frontend-Plugin-Ordner. Sobald eine Komponente neu
installiert oder geändert wird, wird sie gescannt. Erreicht das Urteil die eingestellte Schwelle
(Standard `high`), wird die Komponente in einen Quarantäne-Ordner **verschoben** (nie gelöscht) — und
zwar **bevor** der nächste Home-Assistant-Neustart sie laden kann. Kerngedanke: Herunterladen ≠ Ausführen
— Custom-Integrationen laufen erst, wenn Home Assistant sie lädt, und dieses Zeitfenster ist die Sperre.

> **Baseline-Schutz:** Beim allerersten Start werden alle bereits installierten Komponenten als
> *vertraut* hinterlegt und nie quarantäniert — nur gemeldet. Nur danach installierte oder geänderte
> Komponenten sind quarantäne-fähig, ein laufendes System wird also nie gestört. Findet Marketplace Guard bei
> einem späteren Start eine Komponente, die es noch nie gesehen hat (installiert, während das Add-on
> gestoppt war), gilt sie als neu installiert. Lässt sich der gespeicherte Zustand nicht lesen, wird die
> Baseline neu aufgenommen, und eine Benachrichtigung sagt das.

> **Home Assistant 2026.11 und neuer (Marketplace):** HACS ist jetzt als Marketplace in Home Assistant
> eingebaut und richtet eine neue Integration direkt nach dem Download ein, **ohne Neustart**. Marketplace Guard
> findet und quarantäniert sie weiterhin innerhalb von Sekunden, ihr Code kann aber schon gelaufen sein:
> prüfe ein Repository *vor* der Installation vor (Ebene 2). Nach der Quarantäne einer neuen Integration
> sagt die Benachrichtigung, ob sie in Home Assistant läuft; **Neustart nach Quarantäne einer laufenden
> Integration** startet Home Assistant für dich neu. Updates brauchen weiterhin einen Neustart, daher kann
> **Riskante Updates quarantänieren** (standardmäßig an) ein Update mit neuem Risiko stoppen, bevor es
> geladen wird. HACS
> Guard liest die Aufzeichnungen des Marketplace und bei älteren Home-Assistant-Versionen die von HACS.

**2. Repository-Vorprüfung (vor dem Download)**
Trage eine oder mehrere GitHub-URLs in die Anforderungsdatei ein
(`/homeassistant/marketplace_guard/scan_request.txt`; das Add-on legt sie beim ersten Start mit einer Anleitung
an). Jedes Repository wird in einen temporären Ordner geladen, gescannt (es wird **nicht** installiert)
und gemeldet — so prüfst du ein Repo, *bevor* du es aus HACS oder dem Marketplace installierst. Gescannt
wird, was sie installieren würden: das neueste Release (ohne Release der Hauptzweig) und der
Integrations-Ordner, den sie wählen; der Report nennt beides. Installieren sie ein Release-Paket
(`zip_release`), sagt der Report,
dass dieses Paket nicht gescannt wurde — die installierten Dateien werden bei der Installation ohnehin
gescannt.

**3. KI-Zweitmeinung (optional, standardmäßig aus)**
Nach dem statischen Scan kann eine Home-Assistant-AI-Task die Komponente zusätzlich beurteilen. Sie ist
ein dritter, unabhängiger „Voter", der den statischen Scan *ergänzt* und nie abschwächt.

### Scan-Ebenen
- **pip-audit** — prüft die `manifest.json`-Abhängigkeiten, die auf eine genaue Version festgelegt sind
  (`name==1.2.3`), gegen die Schwachstellen-Datenbank (CVE); eine bekannte Schwachstelle gilt als `high`.
  Dafür wird nichts installiert: nur Name und Version werden nachgeschlagen. Abhängigkeiten mit einem
  Versionsbereich oder ohne Version werden als nicht geprüft aufgeführt.
- **bandit** — statische Analyse des Python-Codes (Shell/Exec, pickle, schwache Krypto, …). Es läuft mit
  Marketplace Guards eigenen Einstellungen: eine Komponente kann keine Prüfung abschalten (`# nosec`,
  `.bandit`-Dateien).
- **Heuristik** — Zugriff auf den HA-Secret-Store / `secrets.yaml`, `eval`/`exec`, Shell-Ausführung,
  Laufzeit-Downloads, Decode-und-Ausführen-Muster, Roh-IP-URLs. Ausgehende Vendor-Hosts sind nur
  *informativ* und heben das Urteil nie an. Python wird so gelesen, wie Python es liest: sein Tokenizer
  erkennt Kommentare und Docstrings, die Text sind und kein Code (außer eine Datei der Komponente liest
  Docstrings, `__doc__`: dann werden sie als Code geprüft), und eine Quelltext-Kodierung, die Code
  verstecken kann (etwa UTF-7), gilt als `high`.
- **Was geladen wird** — `.mjs`/`.cjs`-Skripte und die komprimierten Kopien (`.js.gz`, `.js.br`), die der
  Webserver statt eines Skripts ausliefert, werden geprüft: eine Kopie, die von ihrem Skript abweicht oder
  sich nicht prüfen lässt, gilt als `high`. Symbolische Links aus einer Komponente heraus und
  Spezialdateien gelten als `high` und werden nie gelesen. Dateien werden bis 16 MiB gescannt. Eine
  größere Python-Datei liest Pythons Tokenizer ganz: enthält sie nur Daten (Konstanten wie eingebettete
  Bilder), ist das informativ, sonst gilt sie als `high`. bandit analysiert Python-Dateien bis 2 MiB; eine
  größere wird gemeldet (Code echter Integrationen bleibt weit unter beiden Grenzen).
- **Kompilierter Code** — native Module (`.so`, `.pyd`), Bytecode ohne Quelltext und Bytecode, der ohne
  Prüfung seines Quelltexts läuft, gelten als `high`: Python würde Code ausführen, den niemand prüfen kann.
- **Verstecktes Unicode** — Steuerzeichen für die Schreibrichtung (Trojan Source) in Python-, JavaScript-
  und JSON-Dateien, Kommentare eingeschlossen, gelten als `high`: der Code würde in anderer Reihenfolge
  angezeigt, als er läuft. Unsichtbare Zeichen (Nullbreite) neben gewöhnlichem Text sind in Python
  `medium` und in JavaScript nur informativ; Emoji, persischer oder indischer Text und Übersetzungen
  sind nicht betroffen.
- **Kritische und entfernte Repositories** — die eigene Liste kritischer Repositories von Home Assistant
  und die Listen kritischer und entfernter Repositories des Katalogs (alle sechs Stunden gelesen) gelten
  als `critical`. Lässt sich eine Liste nicht lesen, sagt der Report das.
- **KI-Zweitmeinung** — siehe oben.

### Urteile und Schwellen
Funde werden mit `info` < `low` < `medium` < `high` < `critical` bewertet. Eine Komponente wird
**quarantäniert**, wenn ihr höchster Fund die **Quarantäne-Schwelle** (Standard `high`) erreicht;
darunter löst sie nur eine **Benachrichtigung** aus, sofern sie die **Benachrichtigungs-Schwelle**
(Standard `medium`) erreicht. Reports zu jedem Scan liegen unter `/homeassistant/marketplace_guard/reports/`.
In Benachrichtigungen erscheint Text, der aus einer Komponente stammt (Namen, Hosts, Abhängigkeiten, die
Begründung der KI), als Code und ist so nie ein Link oder eine Formatierung.

### Quarantänierte Komponente wiederherstellen
Quarantäne *verschiebt* die Komponente nur nach `…/_marketplace_quarantine/<name>__<zeitstempel>/` (mit einer
`SCAN_REPORT.txt`). Vertraust du ihr (z. B. ein bekanntes Power-Tool), trage zuerst ihren Ordnernamen
oder ihr Repository in die **Allowlist** ein, verschiebe dann den Ordner zurück nach `custom_components/`
und starte Home Assistant neu. Ohne den Allowlist-Eintrag gilt eine quarantänierte Komponente, die wieder
auftaucht — zurückgeschoben oder von HACS erneut heruntergeladen —, als neue Installation und wird erneut
quarantäniert.

### KI-Zweitmeinung & Datenschutz
Die KI-Prüfung ist **standardmäßig aus**; schalte **KI-Zweitmeinung** ein, um sie zu nutzen. Sie braucht
eine AI-Task-Integration in Home Assistant (ein lokales Modell, z. B. über Ollama, oder einen Cloud-Dienst).
Lass **AI-Task** leer, um die AI-Task-Entität zu nutzen, die Home Assistant bevorzugt, oder trage eine
Entity-ID ein. Das Add-on-Log und das Attribut `ai_task_entities` des Status-Sensors nennen die
vorhandenen AI-Task-Entitäten, das Attribut `ai_review` sagt, ob die Prüfung bereit ist.
**Datenschutz:** der (öffentliche) Quellcode der Komponente und die Scan-Funde gehen an das Modell hinter
der AI-Task; bei einem Cloud-Dienst verlassen sie dein Netz.

Standardmäßig darf die KI nicht allein quarantänieren (`KI darf Quarantäne auslösen` ist aus): ein
„malicious"-Urteil wird nur gemeldet, da kleine lokale Modelle Fehlalarme erzeugen können. Erreicht schon
das statische Urteil die Quarantäne-Schwelle, wird die Komponente sofort quarantäniert, ohne auf die KI zu
warten; die KI kann ein Urteil nur anheben, nie senken. Worauf die KI
besonders achten soll, kannst du in `ai_prompt.txt` im Konfigurationsordner des Add-ons ergänzen
(`addon_configs/<...>_marketplace_guard/`, erreichbar über das Samba-, File-Editor- oder SSH-Add-on; beim ersten
Start mit Beispielen angelegt; Freitext, wird bei jedem Scan an den Prompt angehängt).
Home-Assistant-Integrationen können diesen Ordner nicht beschreiben. Eine Datei `ai_prompt.txt` neben der
Anfragedatei (`/homeassistant/marketplace_guard/`) wird nicht gelesen; enthält sie Anweisungen, bittet dich eine
Benachrichtigung, sie zu verschieben. Die vollständige
KI-Bewertung steht im jeweiligen Komponenten-Report. Die KI sieht zuerst die Zeilen um die statischen
Funde, dann den übrigen Code bis zum **KI-Quellcode-Limit**; bei einer Dashboard-Karte den Anfang ihrer
Skripte. Alles, was aus der Komponente stammt, ist als nicht vertrauenswürdige Daten markiert, und nur die
erste Zeile der Antwort zählt: eine Antwort, die nicht mit der `VERDICT=`-Zeile beginnt, wird als
unbrauchbar gemeldet, statt daraus etwas zu erraten.

Sind Home Assistant oder die AI-Task während einer Prüfung nicht erreichbar (etwa während Home Assistant
neu startet oder solange das Modell nicht läuft), wird die Komponente zuerst nach ihrem statischen Urteil
behandelt und die Prüfung erneut versucht: nach 15 Minuten, 1, 4 und 12 Stunden, danach wird sie
aufgegeben (siehe Log). Das Attribut `ai_review_pending` des Status-Sensors nennt die wartenden
Komponenten. Ein Urteil aus einem erneuten Versuch zählt, wie es beim Scan gezählt hätte; eine neue
Komponente kann also noch quarantäniert werden. Eine fehlende AI-Task-Entität oder eine ausgeschaltete
Prüfung wird nicht wiederholt; das Log sagt, was einzustellen ist.

### Ehrliche Grenzen
Statische Analyse erkennt bekannte verwundbare Abhängigkeiten und verdächtige Muster; sie ist **keine**
Malware-Garantie — ein entschlossener Autor kann sie umgehen. Minifizierte Frontend-Bundles sind statisch
kaum bewertbar, daher ist die JavaScript-Heuristik nur informativ. Die Abhängigkeitsprüfung sieht nur
die Abhängigkeiten, die eine Komponente auf eine genaue Version festlegt, nicht deren eigene
Abhängigkeiten, und braucht eine Verbindung zu PyPI (ohne sie nennt der Report die nicht geprüften
Abhängigkeiten). Seit Home Assistant 2026.11 kann eine neue Integration laufen, bevor Marketplace Guard sie
gescannt hat (siehe oben); die Vorprüfung ist der Weg, vorher hinzusehen. Verstehe Marketplace Guard als
starken Filter und Stolperdraht, nicht als
Sicherheitszertifikat. Wenige, populäre, aktiv gepflegte Repositories zu nutzen bleibt die Grundlage.

### Konfiguration
Alle Optionen sind direkt im **Konfiguration**-Tab beschrieben, und die Standardwerte funktionieren ohne
Änderung: Meldungen erscheinen als persistente Benachrichtigungen in Home Assistant. Ändern willst du
vielleicht die **Benachrichtigungs-Ziele** (einen notify-Dienst wie `mobile_app_<gerät>` für Push
eintragen), die **KI-Zweitmeinung** und für den Marketplace **Riskante Updates quarantänieren**
(standardmäßig an: ein Update mit einem Risiko, das die Version davor nicht hatte, wird quarantäniert, und
die Integration fehlt dann nach dem nächsten Neustart, bis du eine Version installierst, der du vertraust;
ausschalten, um nur benachrichtigt zu werden) und **Neustart nach Quarantäne einer laufenden
Integration**. Ein Ziel, das Home Assistant nicht kennt, wird übersprungen und
im Log (und im Attribut `notify_problems` des Status-Sensors) genannt; ist keines nutzbar, kommen
Meldungen als persistente Benachrichtigung.

Das Log nennt beim Start die Laufzeitumgebung, und der Status-Sensor trägt sie: `python_version`,
`tar_data_filter` (ob Python den `data`-Filter zum Entpacken heruntergeladener Repositories hat),
`bandit_version` und `pip_audit_version` (`missing`, wenn das Werkzeug fehlt) sowie welcher Code läuft:
`code_source` (`built-in`, oder `override` für Code in `code/` im Konfigurationsordner des Add-ons) und
`code_sha256`.
