"""
workout_library.py
------------------
Structured workout definitions for the cycling recommender.

Each Workout contains a steps: list[WorkoutStep] field ready for Garmin
Training API push (via garth). Steps are left empty here — the structure
exists so phase_detector and rules.py can select workouts now and the
Garmin push layer can populate steps later without changing call sites.

Garmin Training API field mapping (for reference when steps are filled in):
    WorkoutStep.step_type        → stepType: "warmup" | "interval" | "recovery" | "cooldown" | "rest"
    WorkoutStep.duration_s       → endConditionType: "time", endConditionValue: duration_s * 1000 (ms)
                                   None → endConditionType: "lapButton"
    WorkoutStep.power_target_low → targetType: "power.zone" → zone boundary watts = low * FTP
    WorkoutStep.power_target_high→ upper boundary watts = high * FTP
    WorkoutStep.cadence_target   → secondaryTargetType: "cadence", secondaryTargetValue: rpm
    WorkoutStep.repeat_count     → wraps the step in a RepeatStep with repeatValue: repeat_count
                                   When repeat_count > 1 on a "work" step, pair it with the
                                   immediately following "recovery" step inside a RepeatStep group.
"""

from dataclasses import dataclass, field


@dataclass
class WorkoutStep:
    name: str                        # display name, e.g. "Warm up", "Threshold"
    step_type: str                   # "warmup" | "work" | "recovery" | "cooldown"
    duration_s: int | None           # seconds; None → open-ended (lap button)
    power_target_low: float | None   # fraction of FTP, e.g. 0.90 = 90%
    power_target_high: float | None  # fraction of FTP, e.g. 1.05 = 105%
    cadence_target: int | None       # rpm; None → no cadence target
    repeat_count: int                # 1 for single steps; >1 pairs this work+next recovery


@dataclass
class Workout:
    name: str
    session_type: str                # e.g. "Zone 2 Endurance", "Threshold Intervals"
    zone_focus: list[str]            # Coggan zone names this workout primarily targets
    tss_min: int
    tss_max: int
    duration_min_h: float
    duration_max_h: float
    description: str
    applicable_phases: list[str]     # "base" | "build" | "peak" | "taper"
    intensity: str                   # "low" | "moderate" | "high"
    steps: list[WorkoutStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Workout library
# Organised roughly by intensity (low → high) within each category.
# ---------------------------------------------------------------------------

WORKOUT_LIBRARY: list[Workout] = [

    # ── Recovery ────────────────────────────────────────────────────────────

    Workout(
        name             = "Active Recovery Spin",
        session_type     = "Recovery",
        zone_focus       = ["Z1 Recovery"],
        tss_min          = 20,
        tss_max          = 35,
        duration_min_h   = 0.75,
        duration_max_h   = 1.25,
        description      = (
            "Unstructured easy spin — keep power in Z1 (<55% FTP, ~183W), "
            "heart rate below 130. Purpose is blood-flow recovery, not adaptation. "
            "If it feels hard, stop."
        ),
        applicable_phases = ["base", "build", "peak", "taper"],
        intensity        = "low",
    ),

    # ── Endurance ───────────────────────────────────────────────────────────

    Workout(
        name             = "Zone 2 Endurance",
        session_type     = "Endurance",
        zone_focus       = ["Z2 Endurance"],
        tss_min          = 55,
        tss_max          = 90,
        duration_min_h   = 1.5,
        duration_max_h   = 2.5,
        description      = (
            "Steady aerobic work at 55–75% FTP (183–250W). "
            "Builds mitochondrial density and fat oxidation. "
            "Seiler's research shows 80% of volume should be here. "
            "Maintain conversation pace — if breathing becomes laboured, back off."
        ),
        applicable_phases = ["base", "build", "peak", "taper"],
        intensity        = "low",
    ),

    Workout(
        name             = "Long Zone 2",
        session_type     = "Long Endurance",
        zone_focus       = ["Z2 Endurance"],
        tss_min          = 100,
        tss_max          = 150,
        duration_min_h   = 3.0,
        duration_max_h   = 5.0,
        description      = (
            "Long aerobic base ride at 55–73% FTP. "
            "Targets fat oxidation and cardiac stroke volume. "
            "The physiological signal requires duration — 3+ hours is where the "
            "adaptation kicks in. Eat well throughout (60–90 g/h carbs). "
            "Core base-phase workout."
        ),
        applicable_phases = ["base", "build"],
        intensity        = "low",
    ),

    # ── Moderate ────────────────────────────────────────────────────────────

    Workout(
        name             = "Aerobic Tempo Blocks",
        session_type     = "Tempo",
        zone_focus       = ["Z3 Tempo"],
        tss_min          = 75,
        tss_max          = 105,
        duration_min_h   = 1.5,
        duration_max_h   = 2.25,
        description      = (
            "3×20 min blocks at 76–83% FTP (253–276W), 5 min easy recovery. "
            "Bridges Z2 endurance and sweet spot — builds lactate clearance without "
            "the recovery cost of threshold work. "
            "Use sparingly: polarised training limits grey-zone time."
        ),
        applicable_phases = ["base", "build"],
        intensity        = "moderate",
    ),

    Workout(
        name             = "Sweet Spot Short",
        session_type     = "Sweet Spot",
        zone_focus       = ["Z3 Tempo", "Z4 Threshold"],
        tss_min          = 70,
        tss_max          = 90,
        duration_min_h   = 1.25,
        duration_max_h   = 1.75,
        description      = (
            "3×10 min at 88–93% FTP (293–310W), 5 min recovery. "
            "Sweet spot sits just below threshold — high training stimulus per "
            "recovery cost. Good for time-crunched sessions. "
            "Targets: sustained power, FTP ceiling lift, muscular endurance."
        ),
        applicable_phases = ["base", "build", "peak"],
        intensity        = "moderate",
    ),

    Workout(
        name             = "Sweet Spot Long",
        session_type     = "Sweet Spot",
        zone_focus       = ["Z3 Tempo", "Z4 Threshold"],
        tss_min          = 90,
        tss_max          = 115,
        duration_min_h   = 1.75,
        duration_max_h   = 2.25,
        description      = (
            "2×20 min at 88–93% FTP (293–310W), 5 min recovery. "
            "Extended sweet spot work. High chronic training benefit with manageable "
            "acute fatigue. Core build-phase workout before progressing to threshold. "
            "Ensure TSB > -20 before attempting."
        ),
        applicable_phases = ["base", "build"],
        intensity        = "moderate",
    ),

    Workout(
        name             = "Taper Activation",
        session_type     = "Activation",
        zone_focus       = ["Z2 Endurance", "Z4 Threshold"],
        tss_min          = 40,
        tss_max          = 60,
        duration_min_h   = 1.0,
        duration_max_h   = 1.5,
        description      = (
            "Warm-up + 4×30 s at 110–115% FTP with 90 s recovery + cool-down. "
            "Maintains neuromuscular activation during taper without accumulating "
            "fatigue. Legs should feel snappy afterwards, not tired. "
            "Key pre-race or pre-event session."
        ),
        applicable_phases = ["taper"],
        intensity        = "moderate",
    ),

    # ── High intensity ───────────────────────────────────────────────────────

    Workout(
        name             = "2×20 Threshold",
        session_type     = "Threshold",
        zone_focus       = ["Z4 Threshold"],
        tss_min          = 85,
        tss_max          = 105,
        duration_min_h   = 1.25,
        duration_max_h   = 1.75,
        description      = (
            "2×20 min at 95–105% FTP (316–350W), 5 min recovery. "
            "Classic threshold workout — holds power at and above FTP to drive "
            "lactate threshold upward. Coggan's foundational Z4 session. "
            "Aim for even splits; negative-split second interval is ideal. "
            "Cadence 85–92 rpm."
        ),
        applicable_phases = ["build", "peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "4×8 Threshold Blocks",
        session_type     = "Threshold Intervals",
        zone_focus       = ["Z4 Threshold"],
        tss_min          = 90,
        tss_max          = 115,
        duration_min_h   = 1.5,
        duration_max_h   = 2.0,
        description      = (
            "4×8 min at 98–106% FTP (326–353W), 4 min recovery. "
            "Shorter intervals allow slightly higher power — builds lactate tolerance "
            "and FTP ceiling. More manageable than 2×20 for early-build phase. "
            "Recovery should be active (50–55% FTP), not stopped."
        ),
        applicable_phases = ["build", "peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "Over-Unders",
        session_type     = "Over-Under Intervals",
        zone_focus       = ["Z4 Threshold", "Z5 VO2max"],
        tss_min          = 90,
        tss_max          = 120,
        duration_min_h   = 1.5,
        duration_max_h   = 2.0,
        description      = (
            "3 sets of: 2 min at 85% FTP → 1 min at 110% FTP, repeated 5×. "
            "5 min recovery between sets. "
            "Trains lactate clearance at threshold — the brief overshoot above FTP "
            "forces the body to process lactate accumulated below, simulating race "
            "surges. Psychologically demanding — use a power meter."
        ),
        applicable_phases = ["build", "peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "5×4 VO2max",
        session_type     = "VO2max Intervals",
        zone_focus       = ["Z5 VO2max"],
        tss_min          = 90,
        tss_max          = 115,
        duration_min_h   = 1.25,
        duration_max_h   = 1.75,
        description      = (
            "5×4 min at 110–120% FTP (366–400W), 4 min recovery. "
            "Targets VO2max — the ceiling on aerobic power. 4 min pushes the body "
            "to near-maximal oxygen uptake without going fully anaerobic. "
            "Cadence 95–105 rpm. Expect respiratory distress in the final 90 s. "
            "Evidence: Billat (2001) — 4 min is the optimal VO2max stimulus duration."
        ),
        applicable_phases = ["build", "peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "8×2 Short VO2max",
        session_type     = "Short Power Intervals",
        zone_focus       = ["Z5 VO2max", "Z6 Anaerobic"],
        tss_min          = 80,
        tss_max          = 105,
        duration_min_h   = 1.25,
        duration_max_h   = 1.75,
        description      = (
            "8×2 min at 115–125% FTP (383–416W), 3 min recovery. "
            "Shorter duration allows higher power — develops anaerobic capacity and "
            "VO2max simultaneously. Good for riders who struggle to maintain "
            "4-min efforts. Pairs well with 5×4 in alternating weeks."
        ),
        applicable_phases = ["build", "peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "30/30 Microbursts",
        session_type     = "Neuromuscular Power",
        zone_focus       = ["Z6 Anaerobic", "Z5 VO2max"],
        tss_min          = 75,
        tss_max          = 100,
        duration_min_h   = 1.0,
        duration_max_h   = 1.5,
        description      = (
            "20× (30 s at 130–140% FTP / 30 s at 50% FTP). "
            "Despite short duration, the repeated near-maximal bursts generate "
            "high metabolic stress. Builds sprint repeatability and anaerobic "
            "capacity. Lower fatigue cost than sustained VO2max work — good for "
            "legs feeling heavy but brain needs a hard session."
        ),
        applicable_phases = ["peak"],
        intensity        = "high",
    ),

    Workout(
        name             = "Race-Day Opener",
        session_type     = "Activation",
        zone_focus       = ["Z2 Endurance", "Z5 VO2max"],
        tss_min          = 30,
        tss_max          = 45,
        duration_min_h   = 0.75,
        duration_max_h   = 1.25,
        description      = (
            "20 min easy + 3×1 min at 110% FTP with 5 min easy between + 15 min cool-down. "
            "The day-before or morning-of session. Opens the legs, primes the "
            "neuromuscular system, and ensures glycogen stores are fully topped up "
            "without adding any fatigue. Do not push past the prescribed power."
        ),
        applicable_phases = ["taper"],
        intensity        = "moderate",
    ),
]
