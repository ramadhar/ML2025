Samsung Device Log Analysis (SDLA)

1) Project purpose
- Analyze issues seen on Samsung devices using device logs.
- Target users: Samsung test engineers and customers support teams.
- Outcomes: Faster triage, clearer root-cause hints, consistent reports, and cross-case pattern discovery.

2) Scope (Focused on Samsung only)
- Inputs: Logs collected from Samsung phones/tablets; no other OEMs.
- Sources supported initially:
  - Android bugreport (zip or txt) exported from the device.
  - Logcat (main/system/events/radio) and kernel (dmesg/kmsg/last_kmsg).
  - ANR traces, tombstones, dropbox crash logs.
  - Device metadata (model, One UI version, build number, baseband) from bugreport header.
  - (Optional) Radio/modem logs when available (diag/QXDM captures), treated as advanced.
- Out of scope initially: Live device collection, cloud uploads, non-Samsung formats.

3) Primary use-cases
- Triage: Summarize the incident, identify error spikes, and propose likely subsystem.
- Root-cause hinting: Map signatures to known issues and firmware versions.
- Reporting: Generate a short human-readable report for tickets (JIRA/ServiceNow).
- Cross-case insights: Identify recurring patterns across models/firmware.

4) Subsystem taxonomy (first pass)
- Apps/Framework (ANR/Crash), SystemUI/One UI, Kernel, Power/Battery/Thermal, Storage/FS,
  Camera/Media, Connectivity (Wi‑Fi/Bluetooth/NFC), Telephony/IMS/VoLTE/5G,
  Sensors/GPS, Security/Knox, DeX/Bixby, Update/OTA, Performance.

5) High-level architecture (planned)
- Ingestion
  - Accepts: folder or zip. Auto-detects bugreport, logcat, tombstones, etc.
  - Unzips safely into data/raw/<case-id> with checksum and size limits.
- Parsing & normalization
  - Parsers per artifact (bugreport header, logcat streams, dmesg, ANR, tombstones).
  - Normalize to a common schema (timestamp, source, component, level, device, text, tags).
  - PII safety: optional redaction of emails, phone numbers, IMSI/IMEI-like patterns.
- Enrichment
  - Extract device model, build/One UI, baseband, uptime, carrier/locale from bugreport.
  - Tokenization, signature hashing of repeating error lines, time bucketing.
- Detection
  - Rule engine (YAML) for known signatures (e.g., “ANR in com.samsung.xxx”).
  - Heuristics for spikes, watchdog resets, thermal throttling, radio attach failures.
  - (Future) ML classifier to predict subsystem/category from features.
- Timeline & report
  - Build a concise incident timeline and impacted components.
  - Emit Markdown/HTML report + CSV/JSON summary for dashboards.

6) Folder layout (repo)
- LogAnalysis/
  - readMe.txt (this file)
  - data/
    - raw/        (input logs per case-id; never committed)
    - processed/  (normalized artifacts; .jsonl/.parquet)
  - rules/        (YAML detection rules/signatures)
  - reports/      (generated outputs)
  - src/          (ingestion, parsers, normalization, detection, report)
  - notebooks/    (exploration and prototyping)
  - tests/        (unit tests for parsers and rules)

7) Minimal workflow (manual, prototype phase)
- Place exported logs into: LogAnalysis/data/raw/<case-id>/
  Examples:
  - <case-id>/bugreport-YYYY-MM-DD-HHMM.zip
  - <case-id>/logcat.txt, dmesg.txt, tombstone_*.txt, traces.txt
- Run analysis (prototype CLI to be added in src/):
  - Ingest → detect artifact types → parse → normalize → detect → report.
- Outputs written to:
  - data/processed/<case-id>/
  - reports/<case-id>.md and reports/<case-id>.html

8) Data contract (normalized event record; draft)
- ts: ISO8601 timestamp (UTC)
- src: log source (logcat-main|system|events|radio|kernel|anr|tombstone|dropbox|meta)
- level: VERBOSE/DEBUG/INFO/WARN/ERROR/FATAL (or kernel level)
- comp: component/tag (e.g., ActivityManager, RILJ, WifiClientMode)
- dev: { model, build, oneui, baseband }
- text: original message line (redacted if enabled)
- sig: optional signature hash/fingerprint for grouping

9) How to collect logs on Samsung
- Bugreport (recommended):
  - Settings → Developer options → Take bug report → Interactive report.
  - Or dialer code *#9900# → Run dumpstate/logcat (varies by model) → copy zip.
- Logcat manually:
  - adb logcat -v threadtime -b all -d > logcat.txt
  - adb shell dmesg > dmesg.txt; adb shell cat /proc/last_kmsg > last_kmsg.txt (if present)
- Ensure customer PII is removed or enable redaction in the tool (planned flag: --redact).

10) Reporting format (target)
- Title, device/build meta, incident summary, key errors (top N signatures),
  timeline (first/last occurrence), suspected subsystem, suggested next steps,
  attachments list, and environment (carrier, region, uptime, battery/thermal state if present).

11) Quality & privacy
- No external uploads. All analysis is local-by-default.
- Optional PII redaction before storing in data/processed.
- Large files are streamed; size/time limits configurable to avoid OOM.

12) Roadmap
- v0.1: Ingestion + parsers for bugreport/logcat/tombstones + Markdown report.
- v0.2: Rules engine (YAML) + HTML report + redaction toggle.
- v0.3: Basic classifier for subsystem prediction + cross-case trend CSV.

13) Getting started (placeholder)
- Tooling will be implemented in src/ with a CLI like:
  - analyze --input data/raw/<case-id> --out reports/ --redact
- Until then, use notebooks/ for exploration and keep raw logs under data/raw.

14) Contributing
- Add new signatures under rules/ as YAML with: id, description, patterns, severity, subsystem.
- Add parser tests for any new artifact types in tests/.

15) Known limitations (current)
- Only Samsung/Android logs; modem logs support is limited.
- Timezone mismatches across sources require normalization.
- Some OEM/private tags may be device-specific and need evolving rules.
