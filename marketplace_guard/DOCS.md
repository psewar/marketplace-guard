# Marketplace Guard

A security tripwire for Home Assistant's Marketplace, HACS and `custom_components`. Home Assistant offers no hook
before a download and no built-in way to check custom integrations for security problems; Marketplace Guard fills that
gap with three layers: a check of every new or changed component, a pre-check of repositories before you install them,
and an optional AI second opinion. Until version 2.0.0 the app (add-on) was called *HACS Guard*.

**[English](#english) · [Deutsch](#deutsch)**

---

## English

### Getting started

1. **Start the app** on its **Info** tab. It starts with Home Assistant by default, so it keeps running after a restart.
   Turn on **Show in sidebar** there to reach its web page from the sidebar (or use **Open web UI**).
2. **What happens on the first start:** Marketplace Guard scans every component that is already installed and records
   it as *trusted* (the baseline). Trusted components are never quarantined, only reported, so a running system is
   never disrupted. When it is done, **one notification sums up**: how many components were recorded, which of them are
   worth a look (a verdict at the notification threshold or above; look at their reports and decide whether you want
   to keep them), the notify services and AI Task entities your Home Assistant has, and how to pre-check a repository.
   The **Log** tab shows each component and its verdict, and the sensor `sensor.marketplace_guard` appears (`0` =
   nothing in quarantine).
3. **Recommended: alerts on your phone.** Alerts appear as notifications in Home Assistant. For push messages, add your
   phone's notify service under **Notification targets** on the **Configuration** tab, next to
   `persistent_notification`. The first notification names the notify services your Home Assistant has (also in the
   status sensor's `notify_targets_available` attribute), for example `mobile_app_example_phone`. Save, then restart the
   app so that it uses the new setting.
4. **Optional: AI second opinion.** If Home Assistant has an AI Task integration (a local model or a cloud service),
   turn on **AI second opinion**; see [AI second opinion and privacy](#ai-second-opinion-and-privacy).

That is all. From now on, every component that is installed or changed is checked.

### Everyday use

#### The web page
**Marketplace Guard** in the sidebar (or **Open web UI** on the Info tab) shows the status, a field to pre-check a
repository, the components in quarantine with their reports and a way to restore them, and the latest reports. Only
administrators see it.

#### When you install or update a component
A component is scanned as soon as its files settle (20 seconds after the last change). Depending on its verdict:

- below the **Notification threshold** (default `medium`): nothing happens, the report is written;
- at the notification threshold: you get a notification;
- at the **Quarantine threshold** (default `high`): the component is **moved** to the quarantine folder (never deleted)
  before the next Home Assistant restart can load it, and you get a notification.

**Home Assistant 2026.11 and later (Marketplace):** HACS is built into Home Assistant as the Marketplace, and it sets up
a new integration right after the download, **without a restart**. Marketplace Guard still finds and quarantines it
within seconds, but its code may already have run, so pre-check a repository *before* you install it, or turn on the
gate (both below). After quarantining a new integration, the notification says whether it is running in Home Assistant;
**Restart after quarantining a running integration** restarts Home Assistant for you. Updates still need a restart, so
**Quarantine risky updates** (on by default) stops an update that brings a new risk before it loads. Marketplace Guard
reads the Marketplace's records, and those of HACS on older versions of Home Assistant.

A component Marketplace Guard finds at a later start without having seen it before (installed while the app was
stopped) counts as newly installed.

#### Stop risky Marketplace installs before they load (optional)
The gate closes the gap above: before anything the Marketplace wrote can load, it asks Marketplace Guard.

1. Turn on **Check Marketplace installs before they load** on the **Configuration** tab, save and restart the app. It
   puts the small integration *Marketplace Guard Gate* into `custom_components` and sends a notification with a link.
2. Restart Home Assistant, then add the integration **Marketplace Guard Gate** (the link in the notification, or
   Settings → Devices & services → Add integration).
3. The status sensor's `marketplace_gate` attribute says `active` within a minute.

An update of Marketplace Guard brings the gate's new version along; Home Assistant loads it at its next restart, and the
version before keeps checking until then. The gate that runs notices its new version within a minute and tells Home
Assistant that a restart is required, naming `marketplace_guard_gate`: Home Assistant shows it, and an automation can
restart at a time that suits you with the trigger or condition *Restart required* (`homeassistant.restart_required`).
A gate older than 2.5.0 does not do this yet; restart once after updating to 2.5.0.

From then on, what Marketplace Guard would quarantine is not installed: the Marketplace puts back what was there (the
version before, for an update), its install dialog says why, and a notification names the component. Its code never
runs. The scan takes a few seconds, and the install dialog waits for it. Integrations and dashboard cards are checked;
themes and templates are not. The AI second opinion follows after the install, as before.

The gate's options (Settings → Devices & services → Marketplace Guard Gate → Configure) say what happens when
Marketplace Guard does not answer (default: refuse, so nothing is installed while the app is stopped) and how long to
wait (120 seconds).

The gate hooks into an internal part of the Marketplace, which a Home Assistant update can change. Then the gate does
not start, a notification says so, and `marketplace_gate` shows `not set up`; until Marketplace Guard is updated,
pre-check repositories before you install them. To turn it off: delete the integration Marketplace Guard Gate, turn the
option off, delete `custom_components/marketplace_guard_gate` and restart Home Assistant.

#### Check a repository before you install it
**On the web page:** type `owner/repo` or the repository's GitHub URL into the field and select **Pre-check**.

**With an action:** run the action `hassio.addon_stdin`, for example under *Developer tools → Actions* in YAML mode:

```yaml
action: hassio.addon_stdin
data:
  addon: <app slug>
  input: owner/repo
```

`<app slug>` is this app's slug: the first notification names it, and so do the status sensor's `app_slug` attribute
and the log. `input` may also be a GitHub URL or a list of up to ten repositories.

For a dashboard, create a script (Settings → Automations & scenes → Scripts → Add script → ⋮ → Edit in YAML) and add
it as a tile; tapping it opens a dialog where you enter the repository and run the script:

```yaml
alias: Pre-check a repository
fields:
  repository:
    name: Repository
    description: owner/repo or a GitHub URL
    required: true
    selector:
      text:
sequence:
  - action: hassio.addon_stdin
    data:
      addon: <app slug>
      input: "{{ repository }}"
```

**With a file:** open `marketplace_guard/scan_request.txt` in your configuration folder (where `configuration.yaml`
is), for example with the **File editor** app, write the repository on a line of its own and save. Marketplace Guard
creates the file with instructions on its first start.

Within seconds the repository is downloaded to a temporary folder and scanned. It is **not** installed. You get a
notification with the verdict, and the report is in `marketplace_guard/reports/`. Anything running in Home Assistant
can run the action, so it can only ask for pre-checks: never quarantine or exempt anything, at most 20 waiting at a
time.

It scans what the Marketplace or HACS would install: the newest release (the default branch if there is none) and the
integration folder they pick; the report says which. If they install a release asset (`zip_release`), the report says
that this asset was not scanned; the installed files are scanned on install anyway.

#### Reports
Every scan writes a report to `marketplace_guard/reports/` in your configuration folder (one file per component or
repository). A quarantined component carries its report as `SCAN_REPORT.txt` in its quarantine folder. In
notifications, text that comes from a component (names, hosts, requirements, the AI's reason) is shown as code, so it is
never a link or formatting.

#### Restore a quarantined component
Quarantine only *moves* a component to `_marketplace_quarantine/<name>__<timestamp>/` in your configuration folder. If
you trust it after reading its report (for example a well-known power tool):

**On the web page:** select **Report and restore** next to it, read the report, type its name and select **Restore**.
The component moves back, and **this copy** is accepted as installed: it is not quarantined again for being back, and a
later change (an update) is checked again. A notification confirms it and names the user who restored it; then restart
Home Assistant to load it. Anything running in Home Assistant could also send this request, as it could already move
the folder back and change the allowlist itself; the notification is there so that a restore you did not make does
not go unnoticed.

**By hand:**

1. Add its folder name (e.g. `my_integration`) or its repository (`owner/repo`) to **Allowlist** on the
   **Configuration** tab and save.
2. Move the folder back to `custom_components/<name>` (a dashboard card to `www/community/<name>`) with the File
   editor, Samba or SSH app, without the `__<timestamp>` part.
3. Restart Home Assistant.

Without the allowlist entry, a quarantined component that appears again (moved back by hand, or downloaded again) counts
as a new install and is quarantined again. Allowlisted components are still scanned and reported, but never
quarantined, also not for a later update.

#### Status sensor
`sensor.marketplace_guard` shows the number of components in quarantine. Its attributes:

| Attribute | Meaning |
|---|---|
| `status` | `ok`, or `alert` while something is in quarantine |
| `quarantined`, `quarantined_count` | the components in quarantine |
| `tracked_components` | how many components Marketplace Guard knows |
| `last_scan_time`, `last_component`, `last_verdict`, `last_action` | the latest scan |
| `notify_targets_available` | the notify services Home Assistant has, for **Notification targets** |
| `app_slug` | this app's slug, for the action `hassio.addon_stdin` |
| `marketplace_gate` | `off`, `active`, `not set up` (restart Home Assistant and add the integration, or see the notification), `unknown` |
| `notify_problems` | notification targets Home Assistant does not have |
| `ai_review`, `ai_task_entities`, `ai_review_pending` | state of the AI second opinion (see [Troubleshooting](#troubleshooting)) |
| `python_version`, `bandit_version`, `pip_audit_version`, `tar_data_filter`, `code_source`, `code_sha256` | what runs |

`sensor.marketplace_guard_last_scan` holds the time of the latest scan. A card for a dashboard:

```yaml
type: entities
title: Marketplace Guard
entities:
  - entity: sensor.marketplace_guard
    name: In quarantine
  - entity: sensor.marketplace_guard_last_scan
    name: Last scan
```

### Configuration

The defaults work without changes. Every option is also described on the **Configuration** tab.

**Options you may want to change**

| Option | Default | What it does |
|---|---|---|
| Notification targets | `persistent_notification` | Where alerts go. Add a notify service such as `mobile_app_<device>` for push messages. A target Home Assistant does not have is skipped and named in the log; if none is usable, alerts fall back to a persistent notification. |
| Quarantine threshold | `high` | Lowest verdict that quarantines a new or changed component. `critical` only quarantines known-malicious repositories; `medium` is stricter. |
| Notification threshold | `medium` | Lowest verdict that notifies without quarantine. |
| Allowlist | empty | Components (folder name) or repositories (`owner/repo`) that are never quarantined. A repository counts only for components the Marketplace or HACS installed. |
| Quarantine risky updates | on | Quarantines an update that brings a risk at the quarantine threshold the version before did not have. The integration is then missing after the next restart until you install a version you trust. Off: such an update is only reported. |
| Restart after quarantining a running integration | off | Restarts Home Assistant at once when a quarantined new integration is already running. Off: the notification asks you to restart. |
| Check Marketplace installs before they load | off | Installs the gate, which refuses what would be quarantined before its code runs (see above). |
| AI second opinion | off | Asks a Home Assistant AI Task to judge new and changed components and pre-checked repositories. |
| AI Task, AI Task fallback | empty | Which AI Task entity to use (empty: the one Home Assistant prefers), and a second one if the first fails. |
| Let AI trigger quarantine | off | Lets an AI verdict of *malicious* quarantine on its own. |

**Other options**

| Option | Default | What it does |
|---|---|---|
| Watched folders | `custom_components`, `www/community` | Folders watched for new and changed components. |
| Quarantine folder | `/homeassistant/_marketplace_quarantine` | Where flagged components are moved to. |
| Scan Python, Scan JavaScript, Run bandit, Run pip-audit | on | The scan layers (see below). |
| Check HACS critical list | on | Reads the public lists of critical and removed repositories online. |
| Scan on start | on | Scans all components when the app starts. |
| Debounce (seconds) | `20` | Wait after the last file change before scanning. |
| Repository pre-check file | `/homeassistant/marketplace_guard/scan_request.txt` | The file for pre-checks. |
| Repository pre-check size limit (MB) | `50` | Largest download for a pre-check. |
| Home Assistant .storage path | `/homeassistant/.storage` | Where the Marketplace's and HACS's records are. |
| Safety-net rescan (minutes) | `360` | Rescans everything regularly in case a file event was missed; `0` turns it off. |
| Status sensor, Status sensor entity id | on, `sensor.marketplace_guard` | The status entity. |
| AI source limit (KB), AI timeout (seconds) | `16`, `120` | How much code the AI sees, and how long to wait for it. |

### How Marketplace Guard checks

**Scan layers**
- **pip-audit**: checks the `manifest.json` requirements that are pinned to an exact version (`name==1.2.3`) against the
  known-vulnerability (CVE) database; a known vulnerability is rated `high`. Nothing is installed for this: only name
  and version are looked up. Requirements given as a range or without a version are listed as not audited.
- **bandit**: static analysis of the Python code (shell and exec, pickle, weak crypto, …). It runs with Marketplace
  Guard's own settings: a component cannot switch checks off (`# nosec`, `.bandit` files).
- **Heuristics**: access to the Home Assistant secret store or `secrets.yaml`, `eval`/`exec`, shell execution, runtime
  downloads, decode-and-execute patterns, raw-IP URLs. Outbound vendor hosts are *informational only* and never raise
  the verdict. Python is read the way Python reads it: its tokenizer finds the comments and the docstrings, which are
  text, not code (unless a file of the component reads docstrings, `__doc__`: then they are scanned as code), and a
  source encoding that can hide code (such as UTF-7) is rated `high`.
- **What is loaded**: `.mjs`/`.cjs` scripts and the compressed copies (`.js.gz`, `.js.br`) the web server sends instead
  of a script are checked: a copy that differs from its script, or one that cannot be reviewed, is rated `high`.
  Symbolic links leaving a component and special files are rated `high` and never read. Files are scanned up to
  16 MiB. A larger Python file is read whole by Python's tokenizer: if it holds only data (constants such as embedded
  images) it is informational, otherwise it is rated `high`. bandit analyses Python files up to 2 MiB; a larger one is
  reported (code of real integrations stays far below both limits).
- **Compiled code**: native modules (`.so`, `.pyd`), bytecode without source, and bytecode marked to run without
  checking its source are rated `high`: Python would run code nobody can review.
- **Hidden Unicode**: bidirectional control characters (Trojan Source) in Python, JavaScript and JSON files, comments
  included, are rated `high`: the code would display in another order than it runs. Invisible characters (zero width)
  next to ordinary text are `medium` in Python and informational in JavaScript; emoji, Persian or Indic text and
  translations are not affected.
- **Critical and removed repositories**: Home Assistant's own list of critical repositories and the catalog's lists of
  critical and removed repositories (read every six hours) are rated `critical`. If a list cannot be read, the report
  says so.

**Verdicts**: findings are rated `info` < `low` < `medium` < `high` < `critical`; a component's verdict is its highest
finding. The thresholds above decide what happens with it.

**Baseline**: if the saved state cannot be read, the baseline is recorded again and a notification says so.

### AI second opinion and privacy
The AI review is **off by default**; turn on **AI second opinion** to use it. It needs an AI Task integration in Home
Assistant (a local model, for example through Ollama, or a cloud service). Leave **AI Task** empty to use the AI Task
entity Home Assistant prefers, or enter an entity id. The app's log and the status sensor's `ai_task_entities`
attribute list the AI Task entities your Home Assistant has, and the `ai_review` attribute says whether the review is
ready. **Privacy:** the component's (public) source code and the scan findings go to the model behind the AI Task; with
a cloud service they leave your network.

By default the AI cannot quarantine on its own (**Let AI trigger quarantine** is off): a malicious AI verdict is only
reported, because small local models can produce false positives. A component whose static verdict already reaches the
quarantine threshold is quarantined at once, without waiting for the AI; the AI can only raise a verdict, never lower
it.

You can steer what the AI focuses on in `ai_prompt.txt` in the app's configuration folder
(`addon_configs/<...>_marketplace_guard/`, reached through the Samba, File editor or SSH app; created with examples on
the first start; free text, appended to the security prompt on every scan). Home Assistant integrations cannot write
that folder. A file `ai_prompt.txt` next to the request file (`marketplace_guard/`) is not read; if it holds
instructions, a notification asks you to move them.

The full AI assessment is saved in the component's report. The AI sees the lines around the static findings first, then
the rest of the code up to **AI source limit**; for a dashboard card, the start of its scripts. Everything taken from
the component is marked as untrusted data, and only the first line of the answer counts: an answer that does not start
with the `VERDICT=` line is reported as unusable instead of being guessed from.

If Home Assistant or the AI Task cannot be reached during a review (for example while Home Assistant restarts, or while
the model is not running), the component is handled on its static verdict first and the review is tried again: after
15 minutes, 1, 4 and 12 hours, then it is given up (see the log). The status sensor's `ai_review_pending` attribute
lists the components waiting. A verdict reached on a retry counts as it would have at the scan, so a new component can
still be quarantined. A missing AI Task entity or a turned-off review is not retried; the log says what to set.

### Limitations
Static analysis catches known-vulnerable dependencies and suspicious patterns; it is **not** a malware guarantee: a
determined author can evade it. Minified frontend bundles are barely analysable statically, so JavaScript heuristics
are informational only. The dependency check sees only the requirements a component pins to an exact version, not the
packages those depend on, and needs a connection to PyPI (without one, the report says which requirements were not
audited). Since Home Assistant 2026.11 a new integration can run before Marketplace Guard has scanned it (see above);
the gate and the pre-check are the ways to look first. Treat Marketplace Guard as a strong filter and tripwire, not a certificate of
safety. Keeping to few, popular, actively maintained repositories remains the foundation.

### Troubleshooting
- **What runs:** the **Log** tab names the runtime at the start, and the status sensor carries it: `python_version`,
  `tar_data_filter` (whether Python has the `data` filter used to unpack downloaded repositories), `bandit_version` and
  `pip_audit_version` (`missing` when the tool is not installed), and which code runs: `code_source` (`built-in`, or
  `override` for code in `code/` of the app's configuration folder) and `code_sha256`.
- **No push messages:** the status sensor's `notify_problems` attribute and the log name targets Home Assistant does not
  have; `notify_targets_available` lists the ones it has.
- **AI review does not run:** the `ai_review` attribute says why: `off` (turned off), `ready`, `no_ai_task_entity`
  (Home Assistant has no AI Task entity), `entity_missing` (none of the entities you entered exists; `ai_task_entities`
  lists the ones there are), `unknown` (Home Assistant could not be asked; the entered entities are tried anyway).
- **A pre-check failed:** the notification and the log say why (for example a repository that does not exist, or one
  larger than the size limit). A request through the action that is not a repository, or one too many while 20 wait,
  is reported as "pre-check request not taken".

---

## Deutsch

### Erste Schritte

1. **App starten** im Tab **Info**. Sie startet standardmäßig mit Home Assistant, läuft also nach einem Neustart weiter.
   Schalte dort **In der Seitenleiste anzeigen** ein, um ihre Webseite aus der Seitenleiste zu öffnen (oder nutze
   **Web-UI öffnen**).
2. **Was beim ersten Start passiert:** Marketplace Guard scannt jede bereits installierte Komponente und hinterlegt sie
   als *vertraut* (die Baseline). Vertraute Komponenten werden nie quarantäniert, nur gemeldet, ein laufendes System
   wird also nie gestört. Danach **fasst eine Benachrichtigung zusammen**: wie viele Komponenten aufgenommen wurden,
   welche davon einen Blick wert sind (ein Urteil ab der Benachrichtigungs-Schwelle; sieh dir ihre Berichte an und
   entscheide, ob du sie behalten willst), welche notify-Dienste und AI-Task-Entitäten dein Home Assistant hat und wie
   du ein Repository vorprüfst. Der Tab **Protokoll** zeigt jede Komponente mit ihrem Urteil, und der Sensor
   `sensor.marketplace_guard` erscheint (`0` = nichts in Quarantäne).
3. **Empfohlen: Meldungen aufs Handy.** Meldungen erscheinen als Benachrichtigungen in Home Assistant. Für
   Push-Nachrichten trägst du im Tab **Konfiguration** unter **Benachrichtigungs-Ziele** den notify-Dienst deines Handys
   ein, neben `persistent_notification`. Die erste Benachrichtigung nennt die notify-Dienste, die dein Home Assistant
   hat (auch im Attribut `notify_targets_available` des Status-Sensors), zum Beispiel `mobile_app_example_phone`.
   Speichern und die App neu starten, damit sie die neue Einstellung nutzt.
4. **Optional: KI-Zweitmeinung.** Hat Home Assistant eine AI-Task-Integration (ein lokales Modell oder einen
   Cloud-Dienst), schalte **KI-Zweitmeinung** ein; siehe [KI-Zweitmeinung und Datenschutz](#ki-zweitmeinung-und-datenschutz).

Das ist alles. Ab jetzt wird jede Komponente geprüft, die installiert oder geändert wird.

### Tägliche Nutzung

#### Die Webseite
**Marketplace Guard** in der Seitenleiste (oder **Web-UI öffnen** im Tab Info) zeigt den Status, ein Feld zum Vorprüfen
eines Repositorys, die Komponenten in Quarantäne mit ihren Berichten und einem Weg, sie wiederherzustellen, und die
neuesten Berichte. Nur Administratoren sehen sie.

#### Wenn du eine Komponente installierst oder aktualisierst
Eine Komponente wird gescannt, sobald ihre Dateien zur Ruhe kommen (20 Sekunden nach der letzten Änderung). Je nach
Urteil:

- unter der **Benachrichtigungs-Schwelle** (Standard `medium`): es passiert nichts, der Bericht wird geschrieben;
- ab der Benachrichtigungs-Schwelle: du bekommst eine Benachrichtigung;
- ab der **Quarantäne-Schwelle** (Standard `high`): die Komponente wird in den Quarantäne-Ordner **verschoben** (nie
  gelöscht), bevor der nächste Neustart von Home Assistant sie laden kann, und du bekommst eine Benachrichtigung.

**Home Assistant 2026.11 und neuer (Marketplace):** HACS ist als Marketplace in Home Assistant eingebaut und richtet
eine neue Integration direkt nach dem Download ein, **ohne Neustart**. Marketplace Guard findet und quarantäniert sie
weiterhin innerhalb von Sekunden, ihr Code kann aber schon gelaufen sein: prüfe ein Repository deshalb *vor* der
Installation, oder schalte die Gate ein (beides unten). Nach der Quarantäne einer neuen Integration sagt die
Benachrichtigung, ob sie in Home Assistant läuft; **Neustart nach Quarantäne einer laufenden Integration** startet Home Assistant für dich neu. Updates
brauchen weiterhin einen Neustart, daher stoppt **Riskante Updates quarantänieren** (standardmäßig an) ein Update mit
neuem Risiko, bevor es geladen wird. Marketplace Guard liest die Aufzeichnungen des Marketplace und bei älteren
Home-Assistant-Versionen die von HACS.

Findet Marketplace Guard bei einem späteren Start eine Komponente, die es noch nie gesehen hat (installiert, während die
App gestoppt war), gilt sie als neu installiert.

#### Riskante Marketplace-Installationen stoppen, bevor sie laden (optional)
Die Gate schließt die Lücke oben: bevor etwas, das der Marketplace geschrieben hat, geladen werden kann, fragt sie
Marketplace Guard.

1. Schalte im Tab **Konfiguration** **Marketplace-Installationen vor dem Laden prüfen** ein, speichere und starte die
   App neu. Sie legt die kleine Integration *Marketplace Guard Gate* nach `custom_components` und schickt eine
   Benachrichtigung mit einem Link.
2. Starte Home Assistant neu und füge dann die Integration **Marketplace Guard Gate** hinzu (der Link in der
   Benachrichtigung, oder Einstellungen → Geräte & Dienste → Integration hinzufügen).
3. Das Attribut `marketplace_gate` des Status-Sensors zeigt innerhalb einer Minute `active`.

Ein Update von Marketplace Guard bringt die neue Version der Gate mit; Home Assistant lädt sie beim nächsten Neustart,
bis dahin prüft die Version davor weiter. Die laufende Gate bemerkt ihre neue Version innerhalb einer Minute und meldet
Home Assistant, dass ein Neustart nötig ist, mit `marketplace_guard_gate` als Grund: Home Assistant zeigt das an, und
eine Automation kann mit dem Auslöser oder der Bedingung *Neustart erforderlich* (`homeassistant.restart_required`) zu
einer passenden Zeit neu starten. Eine Gate vor 2.5.0 kann das noch nicht; starte nach dem Update auf 2.5.0 einmal neu.

Ab dann wird nicht installiert, was Marketplace Guard quarantänieren würde: der Marketplace stellt den vorherigen Stand
wieder her (bei einem Update die Version davor), sein Installationsdialog nennt den Grund, und eine Benachrichtigung
nennt die Komponente. Ihr Code läuft nie. Der Scan dauert ein paar Sekunden, der Installationsdialog wartet darauf.
Geprüft werden Integrationen und Dashboard-Karten, keine Themes und Vorlagen. Die KI-Zweitmeinung folgt wie bisher nach
der Installation.

Die Optionen der Gate (Einstellungen → Geräte & Dienste → Marketplace Guard Gate → Konfigurieren) legen fest, was
passiert, wenn Marketplace Guard nicht antwortet (Standard: ablehnen, solange die App gestoppt ist, wird also nichts
installiert), und wie lange gewartet wird (120 Sekunden).

Die Gate hängt sich in einen internen Teil des Marketplace ein, den ein Home-Assistant-Update ändern kann. Dann startet
die Gate nicht, eine Benachrichtigung sagt das, und `marketplace_gate` zeigt `not set up`; bis Marketplace Guard
aktualisiert ist, prüfe Repositories vor der Installation vor. Zum Abschalten: die Integration Marketplace Guard Gate
löschen, die Option ausschalten, `custom_components/marketplace_guard_gate` löschen und Home Assistant neu starten.

#### Ein Repository vor der Installation prüfen
**Auf der Webseite:** `owner/repo` oder die GitHub-URL des Repositorys in das Feld eintragen und **Pre-check** wählen.

**Mit einer Aktion:** führe die Aktion `hassio.addon_stdin` aus, zum Beispiel unter *Entwicklerwerkzeuge → Aktionen*
im YAML-Modus:

```yaml
action: hassio.addon_stdin
data:
  addon: <app-slug>
  input: owner/repo
```

`<app-slug>` ist der Slug dieser App: die erste Benachrichtigung nennt ihn, ebenso das Attribut `app_slug` des
Status-Sensors und das Protokoll. `input` darf auch eine GitHub-URL oder eine Liste von bis zu zehn Repositories sein.

Für ein Dashboard legst du ein Skript an (Einstellungen → Automationen & Szenen → Skripte → Skript hinzufügen → ⋮ → In
YAML bearbeiten) und fügst es als Kachel hinzu; ein Tippen darauf öffnet einen Dialog, in dem du das Repository
einträgst und das Skript ausführst:

```yaml
alias: Repository vorprüfen
fields:
  repository:
    name: Repository
    description: owner/repo oder eine GitHub-URL
    required: true
    selector:
      text:
sequence:
  - action: hassio.addon_stdin
    data:
      addon: <app-slug>
      input: "{{ repository }}"
```

**Mit einer Datei:** öffne `marketplace_guard/scan_request.txt` in deinem Konfigurationsordner (dort, wo
`configuration.yaml` liegt), zum Beispiel mit der App **File editor**, schreibe das Repository in eine eigene Zeile und
speichere. Marketplace Guard legt die Datei beim ersten Start mit einer Anleitung an.

Innerhalb von Sekunden wird das Repository in einen temporären Ordner geladen und gescannt. Es wird **nicht**
installiert. Du bekommst eine Benachrichtigung mit dem Urteil, und der Bericht liegt in `marketplace_guard/reports/`.
Alles, was in Home Assistant läuft, kann die Aktion ausführen; sie kann deshalb nur Vorprüfungen anfordern: nie etwas
quarantänieren oder freistellen, und höchstens 20 warten gleichzeitig.

Gescannt wird, was der Marketplace oder HACS installieren würden: das neueste Release (ohne Release der Hauptzweig) und
der Integrations-Ordner, den sie wählen; der Bericht nennt beides. Installieren sie ein Release-Paket (`zip_release`),
sagt der Bericht, dass dieses Paket nicht gescannt wurde; die installierten Dateien werden bei der Installation
ohnehin gescannt.

#### Berichte
Jeder Scan schreibt einen Bericht nach `marketplace_guard/reports/` in deinem Konfigurationsordner (eine Datei je
Komponente oder Repository). Eine quarantänierte Komponente trägt ihren Bericht als `SCAN_REPORT.txt` in ihrem
Quarantäne-Ordner. In Benachrichtigungen erscheint Text, der aus einer Komponente stammt (Namen, Hosts,
Abhängigkeiten, die Begründung der KI), als Code und ist so nie ein Link oder eine Formatierung.

#### Eine quarantänierte Komponente wiederherstellen
Quarantäne *verschiebt* eine Komponente nur nach `_marketplace_quarantine/<name>__<zeitstempel>/` in deinem
Konfigurationsordner. Vertraust du ihr, nachdem du ihren Bericht gelesen hast (z. B. ein bekanntes Power-Tool):

**Auf der Webseite:** daneben **Report and restore** wählen, den Bericht lesen, ihren Namen eintippen und **Restore**
wählen. Die Komponente kommt zurück, und **diese Kopie** gilt als installiert: sie wird nicht erneut quarantäniert, nur
weil sie wieder da ist, und eine spätere Änderung (ein Update) wird wieder geprüft. Eine Benachrichtigung bestätigt das
und nennt den Benutzer, der sie wiederhergestellt hat; danach Home Assistant neu starten, um sie zu laden. Alles, was in
Home Assistant läuft, könnte diese Anfrage ebenfalls schicken, so wie es den Ordner auch selbst zurückschieben und die
Allowlist ändern könnte; die Benachrichtigung sorgt dafür, dass eine Wiederherstellung, die du nicht selbst gemacht
hast, nicht unbemerkt bleibt.

**Von Hand:**

1. Trage ihren Ordnernamen (z. B. `my_integration`) oder ihr Repository (`owner/repo`) im Tab **Konfiguration** in die
   **Allowlist** ein und speichere.
2. Verschiebe den Ordner zurück nach `custom_components/<name>` (eine Dashboard-Karte nach `www/community/<name>`), mit
   der File-editor-, Samba- oder SSH-App, ohne den Teil `__<zeitstempel>`.
3. Starte Home Assistant neu.

Ohne den Allowlist-Eintrag gilt eine quarantänierte Komponente, die wieder auftaucht (von Hand zurückgeschoben oder
erneut heruntergeladen), als neue Installation und wird erneut quarantäniert. Komponenten auf der Allowlist werden
trotzdem gescannt und gemeldet, aber nie quarantäniert, auch nicht bei einem späteren Update.

#### Status-Sensor
`sensor.marketplace_guard` zeigt, wie viele Komponenten in Quarantäne sind. Seine Attribute:

| Attribut | Bedeutung |
|---|---|
| `status` | `ok`, oder `alert`, solange etwas in Quarantäne ist |
| `quarantined`, `quarantined_count` | die Komponenten in Quarantäne |
| `tracked_components` | wie viele Komponenten Marketplace Guard kennt |
| `last_scan_time`, `last_component`, `last_verdict`, `last_action` | der letzte Scan |
| `notify_targets_available` | die notify-Dienste, die Home Assistant hat, für **Benachrichtigungs-Ziele** |
| `app_slug` | der Slug dieser App, für die Aktion `hassio.addon_stdin` |
| `marketplace_gate` | `off`, `active`, `not set up` (Home Assistant neu starten und die Integration hinzufügen, oder siehe die Benachrichtigung), `unknown` |
| `notify_problems` | Benachrichtigungs-Ziele, die Home Assistant nicht hat |
| `ai_review`, `ai_task_entities`, `ai_review_pending` | Stand der KI-Zweitmeinung (siehe [Fehlersuche](#fehlersuche)) |
| `python_version`, `bandit_version`, `pip_audit_version`, `tar_data_filter`, `code_source`, `code_sha256` | was läuft |

`sensor.marketplace_guard_last_scan` enthält die Zeit des letzten Scans. Eine Karte fürs Dashboard:

```yaml
type: entities
title: Marketplace Guard
entities:
  - entity: sensor.marketplace_guard
    name: In Quarantäne
  - entity: sensor.marketplace_guard_last_scan
    name: Letzter Scan
```

### Konfiguration

Die Standardwerte funktionieren ohne Änderung. Jede Option ist auch im Tab **Konfiguration** beschrieben.

**Optionen, die du vielleicht ändern willst**

| Option | Standard | Was sie tut |
|---|---|---|
| Benachrichtigungs-Ziele | `persistent_notification` | Wohin Meldungen gehen. Für Push einen notify-Dienst wie `mobile_app_<gerät>` eintragen. Ein Ziel, das Home Assistant nicht hat, wird übersprungen und im Protokoll genannt; ist keines nutzbar, kommen Meldungen als persistente Benachrichtigung. |
| Quarantäne-Schwelle | `high` | Niedrigstes Urteil, das eine neue oder geänderte Komponente quarantäniert. `critical` quarantäniert nur bekannt bösartige Repositories; `medium` ist strenger. |
| Benachrichtigungs-Schwelle | `medium` | Niedrigstes Urteil, das ohne Quarantäne benachrichtigt. |
| Allowlist | leer | Komponenten (Ordnername) oder Repositories (`owner/repo`), die nie quarantäniert werden. Ein Repository zählt nur für Komponenten, die der Marketplace oder HACS installiert hat. |
| Riskante Updates quarantänieren | an | Quarantäniert ein Update, das ein Risiko ab der Quarantäne-Schwelle mitbringt, das die Version davor nicht hatte. Die Integration fehlt dann nach dem nächsten Neustart, bis du eine Version installierst, der du vertraust. Aus: ein solches Update wird nur gemeldet. |
| Neustart nach Quarantäne einer laufenden Integration | aus | Startet Home Assistant sofort neu, wenn eine quarantänierte neue Integration schon läuft. Aus: die Benachrichtigung bittet dich um den Neustart. |
| Marketplace-Installationen vor dem Laden prüfen | aus | Installiert die Gate, die ablehnt, was quarantäniert würde, bevor sein Code läuft (siehe oben). |
| KI-Zweitmeinung | aus | Lässt eine AI-Task von Home Assistant neue und geänderte Komponenten und vorgeprüfte Repositories beurteilen. |
| AI-Task, KI-Task-Fallback | leer | Welche AI-Task-Entität genutzt wird (leer: die, die Home Assistant bevorzugt), und eine zweite, falls die erste scheitert. |
| KI darf Quarantäne auslösen | aus | Lässt ein KI-Urteil *malicious* allein quarantänieren. |

**Weitere Optionen**

| Option | Standard | Was sie tut |
|---|---|---|
| Überwachte Ordner | `custom_components`, `www/community` | Ordner, die auf neue und geänderte Komponenten überwacht werden. |
| Quarantäne-Ordner | `/homeassistant/_marketplace_quarantine` | Wohin auffällige Komponenten verschoben werden. |
| Python scannen, JavaScript scannen, bandit ausführen, pip-audit ausführen | an | Die Scan-Ebenen (siehe unten). |
| HACS-Critical-Liste prüfen | an | Liest die öffentlichen Listen kritischer und entfernter Repositories online. |
| Beim Start scannen | an | Scannt alle Komponenten, wenn die App startet. |
| Entprellung (Sekunden) | `20` | Wartezeit nach der letzten Dateiänderung bis zum Scan. |
| Repo-Vorprüfungs-Datei | `/homeassistant/marketplace_guard/scan_request.txt` | Die Datei für Vorprüfungen. |
| Repo-Vorprüfung Größenlimit (MB) | `50` | Größter Download für eine Vorprüfung. |
| Home-Assistant-.storage-Pfad | `/homeassistant/.storage` | Wo die Aufzeichnungen des Marketplace und von HACS liegen. |
| Sicherheitsnetz-Rescan (Minuten) | `360` | Scannt regelmäßig alles neu, falls ein Dateiereignis verpasst wurde; `0` schaltet das ab. |
| Status-Sensor, Status-Sensor Entity-ID | an, `sensor.marketplace_guard` | Die Status-Entität. |
| KI-Quellcode-Limit (KB), KI-Timeout (Sekunden) | `16`, `120` | Wie viel Code die KI sieht und wie lange auf sie gewartet wird. |

### Wie Marketplace Guard prüft

**Scan-Ebenen**
- **pip-audit**: prüft die `manifest.json`-Abhängigkeiten, die auf eine genaue Version festgelegt sind (`name==1.2.3`),
  gegen die Schwachstellen-Datenbank (CVE); eine bekannte Schwachstelle gilt als `high`. Dafür wird nichts installiert:
  nur Name und Version werden nachgeschlagen. Abhängigkeiten mit einem Versionsbereich oder ohne Version werden als
  nicht geprüft aufgeführt.
- **bandit**: statische Analyse des Python-Codes (Shell und Exec, pickle, schwache Krypto, …). Es läuft mit Marketplace
  Guards eigenen Einstellungen: eine Komponente kann keine Prüfung abschalten (`# nosec`, `.bandit`-Dateien).
- **Heuristik**: Zugriff auf den Secret-Store von Home Assistant oder `secrets.yaml`, `eval`/`exec`,
  Shell-Ausführung, Laufzeit-Downloads, Decode-und-Ausführen-Muster, Roh-IP-URLs. Ausgehende Vendor-Hosts sind nur
  *informativ* und heben das Urteil nie an. Python wird so gelesen, wie Python es liest: sein Tokenizer erkennt
  Kommentare und Docstrings, die Text sind und kein Code (außer eine Datei der Komponente liest Docstrings, `__doc__`:
  dann werden sie als Code geprüft), und eine Quelltext-Kodierung, die Code verstecken kann (etwa UTF-7), gilt als
  `high`.
- **Was geladen wird**: `.mjs`/`.cjs`-Skripte und die komprimierten Kopien (`.js.gz`, `.js.br`), die der Webserver
  statt eines Skripts ausliefert, werden geprüft: eine Kopie, die von ihrem Skript abweicht oder sich nicht prüfen
  lässt, gilt als `high`. Symbolische Links aus einer Komponente heraus und Spezialdateien gelten als `high` und werden
  nie gelesen. Dateien werden bis 16 MiB gescannt. Eine größere Python-Datei liest Pythons Tokenizer ganz: enthält sie
  nur Daten (Konstanten wie eingebettete Bilder), ist das informativ, sonst gilt sie als `high`. bandit analysiert
  Python-Dateien bis 2 MiB; eine größere wird gemeldet (Code echter Integrationen bleibt weit unter beiden Grenzen).
- **Kompilierter Code**: native Module (`.so`, `.pyd`), Bytecode ohne Quelltext und Bytecode, der ohne Prüfung seines
  Quelltexts läuft, gelten als `high`: Python würde Code ausführen, den niemand prüfen kann.
- **Verstecktes Unicode**: Steuerzeichen für die Schreibrichtung (Trojan Source) in Python-, JavaScript- und
  JSON-Dateien, Kommentare eingeschlossen, gelten als `high`: der Code würde in anderer Reihenfolge angezeigt, als er
  läuft. Unsichtbare Zeichen (Nullbreite) neben gewöhnlichem Text sind in Python `medium` und in JavaScript nur
  informativ; Emoji, persischer oder indischer Text und Übersetzungen sind nicht betroffen.
- **Kritische und entfernte Repositories**: die eigene Liste kritischer Repositories von Home Assistant und die Listen
  kritischer und entfernter Repositories des Katalogs (alle sechs Stunden gelesen) gelten als `critical`. Lässt sich
  eine Liste nicht lesen, sagt der Bericht das.

**Urteile**: Funde werden mit `info` < `low` < `medium` < `high` < `critical` bewertet; das Urteil einer Komponente ist
ihr höchster Fund. Die Schwellen oben entscheiden, was damit geschieht.

**Baseline**: lässt sich der gespeicherte Zustand nicht lesen, wird die Baseline neu aufgenommen, und eine
Benachrichtigung sagt das.

### KI-Zweitmeinung und Datenschutz
Die KI-Prüfung ist **standardmäßig aus**; schalte **KI-Zweitmeinung** ein, um sie zu nutzen. Sie braucht eine
AI-Task-Integration in Home Assistant (ein lokales Modell, z. B. über Ollama, oder einen Cloud-Dienst). Lass **AI-Task**
leer, um die AI-Task-Entität zu nutzen, die Home Assistant bevorzugt, oder trage eine Entity-ID ein. Das Protokoll der
App und das Attribut `ai_task_entities` des Status-Sensors nennen die vorhandenen AI-Task-Entitäten, das Attribut
`ai_review` sagt, ob die Prüfung bereit ist. **Datenschutz:** der (öffentliche) Quellcode der Komponente und die
Scan-Funde gehen an das Modell hinter der AI-Task; bei einem Cloud-Dienst verlassen sie dein Netz.

Standardmäßig darf die KI nicht allein quarantänieren (**KI darf Quarantäne auslösen** ist aus): ein
„malicious“-Urteil wird nur gemeldet, da kleine lokale Modelle Fehlalarme erzeugen können. Erreicht schon das statische
Urteil die Quarantäne-Schwelle, wird die Komponente sofort quarantäniert, ohne auf die KI zu warten; die KI kann ein
Urteil nur anheben, nie senken.

Worauf die KI besonders achten soll, kannst du in `ai_prompt.txt` im Konfigurationsordner der App ergänzen
(`addon_configs/<...>_marketplace_guard/`, erreichbar über die Samba-, File-editor- oder SSH-App; beim ersten Start mit
Beispielen angelegt; Freitext, wird bei jedem Scan an den Prompt angehängt). Home-Assistant-Integrationen können diesen
Ordner nicht beschreiben. Eine Datei `ai_prompt.txt` neben der Anfragedatei (`marketplace_guard/`) wird nicht gelesen;
enthält sie Anweisungen, bittet dich eine Benachrichtigung, sie zu verschieben.

Die vollständige KI-Bewertung steht im Bericht der Komponente. Die KI sieht zuerst die Zeilen um die statischen Funde,
dann den übrigen Code bis zum **KI-Quellcode-Limit**; bei einer Dashboard-Karte den Anfang ihrer Skripte. Alles, was aus
der Komponente stammt, ist als nicht vertrauenswürdige Daten markiert, und nur die erste Zeile der Antwort zählt: eine
Antwort, die nicht mit der `VERDICT=`-Zeile beginnt, wird als unbrauchbar gemeldet, statt daraus etwas zu erraten.

Sind Home Assistant oder die AI-Task während einer Prüfung nicht erreichbar (etwa während Home Assistant neu startet
oder solange das Modell nicht läuft), wird die Komponente zuerst nach ihrem statischen Urteil behandelt und die Prüfung
erneut versucht: nach 15 Minuten, 1, 4 und 12 Stunden, danach wird sie aufgegeben (siehe Protokoll). Das Attribut
`ai_review_pending` des Status-Sensors nennt die wartenden Komponenten. Ein Urteil aus einem erneuten Versuch zählt, wie
es beim Scan gezählt hätte; eine neue Komponente kann also noch quarantäniert werden. Eine fehlende AI-Task-Entität oder
eine ausgeschaltete Prüfung wird nicht wiederholt; das Protokoll sagt, was einzustellen ist.

### Grenzen
Statische Analyse erkennt bekannte verwundbare Abhängigkeiten und verdächtige Muster; sie ist **keine**
Malware-Garantie: ein entschlossener Autor kann sie umgehen. Minifizierte Frontend-Bundles sind statisch kaum
bewertbar, daher ist die JavaScript-Heuristik nur informativ. Die Abhängigkeitsprüfung sieht nur die Abhängigkeiten,
die eine Komponente auf eine genaue Version festlegt, nicht deren eigene Abhängigkeiten, und braucht eine Verbindung zu
PyPI (ohne sie nennt der Bericht die nicht geprüften Abhängigkeiten). Seit Home Assistant 2026.11 kann eine neue
Integration laufen, bevor Marketplace Guard sie gescannt hat (siehe oben); die Gate und die Vorprüfung sind die Wege,
vorher hinzusehen. Verstehe Marketplace Guard als starken Filter und Stolperdraht, nicht als Sicherheitszertifikat. Wenige,
populäre, aktiv gepflegte Repositories zu nutzen bleibt die Grundlage.

### Fehlersuche
- **Was läuft:** Der Tab **Protokoll** nennt beim Start die Laufzeitumgebung, und der Status-Sensor trägt sie:
  `python_version`, `tar_data_filter` (ob Python den `data`-Filter zum Entpacken heruntergeladener Repositories hat),
  `bandit_version` und `pip_audit_version` (`missing`, wenn das Werkzeug fehlt) sowie welcher Code läuft: `code_source`
  (`built-in`, oder `override` für Code in `code/` im Konfigurationsordner der App) und `code_sha256`.
- **Keine Push-Nachrichten:** Das Attribut `notify_problems` des Status-Sensors und das Protokoll nennen Ziele, die Home
  Assistant nicht hat; `notify_targets_available` nennt die vorhandenen.
- **Die KI-Prüfung läuft nicht:** Das Attribut `ai_review` sagt, warum: `off` (ausgeschaltet), `ready` (bereit),
  `no_ai_task_entity` (Home Assistant hat keine AI-Task-Entität), `entity_missing` (keine der eingetragenen Entitäten
  gibt es; `ai_task_entities` nennt die vorhandenen), `unknown` (Home Assistant ließ sich nicht fragen; die eingetragenen
  Entitäten werden trotzdem versucht).
- **Eine Vorprüfung ist gescheitert:** Die Benachrichtigung und das Protokoll sagen, warum (zum Beispiel ein
  Repository, das es nicht gibt, oder eines über dem Größenlimit). Eine Anfrage über die Aktion, die kein Repository
  ist, oder eine zu viel, während 20 warten, wird als „pre-check request not taken“ gemeldet.
