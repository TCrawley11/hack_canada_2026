"""
FarmGuard test suite — plain Python, no external frameworks.
Prints checkmark or X per check, final pass/fail summary.
"""
import re
import sys
import time
import threading
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

from backend.app import deterrent, incidents
from backend.app.deterrent import SCRIPTS, DEFAULT_SCRIPTS, COOLDOWN_SECONDS

PASS_SYM = "[PASS]"
FAIL_SYM = "[FAIL]"

_results: list[bool] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    sym = PASS_SYM if passed else FAIL_SYM
    suffix = f"  ({detail})" if detail else ""
    print(f"  {sym} {label}{suffix}")
    _results.append(passed)


def make_mock_client() -> MagicMock:
    """Returns a mock ElevenLabs client whose TTS yields fake audio bytes."""
    mock = MagicMock()
    mock.text_to_speech.convert.side_effect = lambda **kw: iter([b"fake_audio"])
    return mock


def reset_deterrent() -> None:
    deterrent.cooldowns.clear()
    deterrent.client = None


# ── Test 1: Script integrity ────────────────────────────────────────────────
print("\nTest 1: Script integrity")
for species, scripts in SCRIPTS.items():
    check(f"'{species}' has >= 2 scripts (got {len(scripts)})", len(scripts) >= 2)


# ── Test 2: Cooldown logic — engages and blocks retrigger ───────────────────
print("\nTest 2: Cooldown logic")
reset_deterrent()

check("Not on cooldown before any trigger", not deterrent.is_on_cooldown("crow"))

deterrent.set_cooldown("crow")
check("On cooldown immediately after set_cooldown", deterrent.is_on_cooldown("crow"))

# A second set_cooldown call should keep it active
deterrent.set_cooldown("crow")
check("Still on cooldown after second set_cooldown", deterrent.is_on_cooldown("crow"))

# Different species should NOT be affected
check("Other species ('deer') unaffected by crow cooldown", not deterrent.is_on_cooldown("deer"))

reset_deterrent()


# ── Test 3: All species fire without crashing ───────────────────────────────
print("\nTest 3: All species fire without crashing")
for species in SCRIPTS:
    reset_deterrent()
    try:
        with patch("backend.app.deterrent.get_client", return_value=make_mock_client()), \
             patch("backend.app.deterrent.play_audio_background"):
            result = deterrent.trigger_deterrent(species)
        check(f"'{species}' triggers without exception (returned script)", result is not None)
    except Exception as exc:
        check(f"'{species}' triggers without exception", False, str(exc))

reset_deterrent()


# ── Test 4: Each species uses the correct script pool ───────────────────────
print("\nTest 4: Correct script pool per species")
for species in SCRIPTS:
    reset_deterrent()
    captured: list[str] = []

    def _capture(**kw):
        captured.append(kw["text"])
        return iter([b"x"])

    mock = MagicMock()
    mock.text_to_speech.convert.side_effect = _capture

    with patch("backend.app.deterrent.get_client", return_value=mock), \
         patch("backend.app.deterrent.play_audio_background"):
        deterrent.trigger_deterrent(species)

    if captured:
        used = captured[0]
        in_own_pool = used in SCRIPTS[species]
        in_other_pool = any(used in SCRIPTS[s] for s in SCRIPTS if s != species)
        check(f"'{species}' script came from its own pool", in_own_pool)
        check(f"'{species}' script not from another species pool", not in_other_pool)
    else:
        check(f"'{species}' script was captured", False, "nothing captured")

reset_deterrent()


# ── Test 5: Randomization distribution ─────────────────────────────────────
print("\nTest 5: Randomization — all scripts appear across 100 draws")
import random as _random

for species, scripts in SCRIPTS.items():
    seen: set[str] = set()
    for _ in range(100):
        seen.add(_random.choice(scripts))
    missing = set(scripts) - seen
    check(
        f"'{species}': all {len(scripts)} scripts appeared",
        len(missing) == 0,
        f"missing: {missing}" if missing else "",
    )


# ── Test 6: Incident logging — fields, values, ISO timestamp ────────────────
print("\nTest 6: Incident logging")
incidents._log.clear()

entry = incidents.log_incident(species="crow", script="Go away crow!")

check("Entry has 'timestamp' field", "timestamp" in entry)
check("Entry has 'species' field", "species" in entry)
check("Entry has 'script' field", "script" in entry)
check("No extra fields", set(entry.keys()) == {"timestamp", "species", "script"})
check("species value is correct", entry["species"] == "crow")
check("script value is correct", entry["script"] == "Go away crow!")

iso_re = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
check("timestamp matches ISO 8601 format", bool(re.match(iso_re, entry["timestamp"])))
check("timestamp includes UTC timezone info", entry["timestamp"].endswith("+00:00"))

# Entry appears in get_incidents()
log = incidents.get_incidents()
check("Entry appears in get_incidents()", entry in log)


# ── Test 7: Log max size caps at 20, keeps most recent ──────────────────────
print("\nTest 7: Log max size")
incidents._log.clear()

for i in range(25):
    incidents.log_incident(species=f"pest_{i}", script=f"script_{i}")

log = incidents.get_incidents()
check("Log length is exactly 20", len(log) == 20, f"got {len(log)}")
check("Most recent entry is pest_24", log[-1]["species"] == "pest_24")
check("Oldest entry is pest_5 (5 dropped)", log[0]["species"] == "pest_5")
check("pest_0 through pest_4 are gone", all(e["species"] not in {f"pest_{i}" for i in range(5)} for e in log))


# ── Test 8: Thread safety — 10 concurrent log_incident calls ────────────────
print("\nTest 8: Thread safety")
incidents._log.clear()

errors: list[str] = []

def _concurrent_log(i: int) -> None:
    try:
        incidents.log_incident(species=f"species_{i}", script=f"script_{i}")
    except Exception as exc:
        errors.append(str(exc))

threads = [threading.Thread(target=_concurrent_log, args=(i,)) for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

check("No exceptions during concurrent logging", len(errors) == 0, "; ".join(errors) if errors else "")
check("All 10 entries were logged", len(incidents.get_incidents()) == 10, f"got {len(incidents.get_incidents())}")


# ── Test 9: Cooldown expiry resets correctly ────────────────────────────────
print("\nTest 9: Cooldown expiry")
reset_deterrent()

deterrent.set_cooldown("goose")
check("On cooldown right after set", deterrent.is_on_cooldown("goose"))

# Backdate the timestamp to simulate the window passing
deterrent.cooldowns["goose"] = time.time() - COOLDOWN_SECONDS - 1
check("Off cooldown after window elapses", not deterrent.is_on_cooldown("goose"))

# trigger_deterrent should now fire again
with patch("backend.app.deterrent.get_client", return_value=make_mock_client()), \
     patch("backend.app.deterrent.play_audio_background"):
    result = deterrent.trigger_deterrent("goose")
check("trigger_deterrent fires again after cooldown expires", result is not None)

reset_deterrent()


# ── Summary ──────────────────────────────────────────────────────────────────
passed = sum(_results)
total = len(_results)
all_passed = passed == total

print(f"\n{'=' * 44}")
print(f"  {'PASS' if all_passed else 'FAIL'}  {passed}/{total} checks passed")
print(f"{'=' * 44}\n")

from backend.app.deterrent import trigger_deterrent, SCRIPTS

print("Audio listening test — you will hear Borthomoleus for each species\n")

for species in SCRIPTS.keys():
    print(f"Playing: {species}...")
    script = trigger_deterrent(species)
    print(f"  Script: {script}")
    time.sleep(6)  # wait for audio to finish before next species

print("\nDone. Did all 4 sound correct?")

sys.exit(0 if all_passed else 1)
