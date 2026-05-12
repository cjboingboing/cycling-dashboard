"""
workout_library.py
------------------
Structured workout definitions for the cycling recommender.

Garmin Training API field mapping (garmin_push.py handles the conversion):
    WorkoutStep.step_type        -> stepType: "warmup"|"interval"|"recovery"|"cooldown"
    WorkoutStep.duration_s       -> endConditionType: "time", endConditionValue: duration_s * 1000 (ms)
                                    None -> endConditionType: "lapButton"
    WorkoutStep.power_target_low -> targetType: "power.zone", lower boundary watts = low * FTP
    WorkoutStep.power_target_high-> upper boundary watts = high * FTP
    WorkoutStep.repeat_count     -> wraps the step in a RepeatStep with the immediately
                                    following "recovery" step as the paired rest.
"""

from dataclasses import dataclass, field


@dataclass
class WorkoutStep:
    name: str                        # display name, e.g. "Warm up", "Threshold"
    step_type: str                   # "warmup" | "work" | "recovery" | "cooldown"
    duration_s: int | None           # seconds; None -> open-ended (lap button)
    power_target_low: float | None   # fraction of FTP, e.g. 0.90 = 90%
    power_target_high: float | None  # fraction of FTP, e.g. 1.05 = 105%
    cadence_target: int | None       # rpm; None -> no cadence target
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
# Workout library — ordered low to high intensity
# ---------------------------------------------------------------------------

WORKOUT_LIBRARY: list[Workout] = [

    # -- Recovery ------------------------------------------------------------

    Workout(
        name              = "Active Recovery Spin",
        session_type      = "Recovery",
        zone_focus        = ["Z1 Recovery"],
        tss_min           = 20,
        tss_max           = 35,
        duration_min_h    = 0.75,
        duration_max_h    = 1.25,
        description       = (
            "Unstructured easy spin -- keep power in Z1 (<55% FTP), "
            "heart rate below 130. Purpose is blood-flow recovery, not adaptation. "
            "If it feels hard, stop."
        ),
        applicable_phases = ["base", "build", "peak", "taper"],
        intensity         = "low",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   600,  0.40, 0.50, None, 1),
            WorkoutStep("Easy spin", "work",     2700, 0.40, 0.54, 85,   1),
            WorkoutStep("Cool down", "cooldown", 300,  0.35, 0.45, None, 1),
        ],
    ),

    # -- Endurance -----------------------------------------------------------

    Workout(
        name              = "Zone 2 Endurance",
        session_type      = "Endurance",
        zone_focus        = ["Z2 Endurance"],
        tss_min           = 55,
        tss_max           = 90,
        duration_min_h    = 1.5,
        duration_max_h    = 2.5,
        description       = (
            "Steady aerobic work at 55-75% FTP. "
            "Builds mitochondrial density and fat oxidation. "
            "Seiler's research shows 80% of volume should be here. "
            "Maintain conversation pace -- if breathing becomes laboured, back off."
        ),
        applicable_phases = ["base", "build", "peak", "taper"],
        intensity         = "low",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   600,  0.45, 0.54, None, 1),
            WorkoutStep("Zone 2",    "work",     5400, 0.55, 0.75, 88,   1),
            WorkoutStep("Cool down", "cooldown", 600,  0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Long Zone 2",
        session_type      = "Long Endurance",
        zone_focus        = ["Z2 Endurance"],
        tss_min           = 100,
        tss_max           = 150,
        duration_min_h    = 3.0,
        duration_max_h    = 5.0,
        description       = (
            "Long aerobic base ride at 55-73% FTP. "
            "Targets fat oxidation and cardiac stroke volume. "
            "The physiological signal requires duration -- 3+ hours is where the "
            "adaptation kicks in. Eat well throughout (60-90 g/h carbs)."
        ),
        applicable_phases = ["base", "build"],
        intensity         = "low",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900,   0.45, 0.54, None, 1),
            WorkoutStep("Zone 2",    "work",     10800, 0.55, 0.73, 88,   1),
            WorkoutStep("Cool down", "cooldown", 900,   0.40, 0.50, None, 1),
        ],
    ),

    # -- Moderate ------------------------------------------------------------

    Workout(
        name              = "Aerobic Tempo Blocks",
        session_type      = "Tempo",
        zone_focus        = ["Z3 Tempo"],
        tss_min           = 75,
        tss_max           = 105,
        duration_min_h    = 1.5,
        duration_max_h    = 2.25,
        description       = (
            "3x20 min blocks at 76-83% FTP, 5 min easy recovery. "
            "Bridges Z2 endurance and sweet spot -- builds lactate clearance. "
            "Use sparingly: polarised training limits grey-zone time."
        ),
        applicable_phases = ["base", "build"],
        intensity         = "moderate",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900,  0.45, 0.54, None, 1),
            WorkoutStep("Tempo",     "work",     1200, 0.76, 0.83, 88,   3),
            WorkoutStep("Recovery",  "recovery", 300,  0.45, 0.54, 80,   1),
            WorkoutStep("Cool down", "cooldown", 600,  0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Sweet Spot Short",
        session_type      = "Sweet Spot",
        zone_focus        = ["Z3 Tempo", "Z4 Threshold"],
        tss_min           = 70,
        tss_max           = 90,
        duration_min_h    = 1.25,
        duration_max_h    = 1.75,
        description       = (
            "3x10 min at 88-93% FTP, 5 min recovery. "
            "High training stimulus per recovery cost. Good for time-crunched sessions."
        ),
        applicable_phases = ["base", "build", "peak"],
        intensity         = "moderate",
        steps             = [
            WorkoutStep("Warm up",    "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("Sweet Spot", "work",     600, 0.88, 0.93, 90,   3),
            WorkoutStep("Recovery",   "recovery", 300, 0.45, 0.54, 80,   1),
            WorkoutStep("Cool down",  "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Sweet Spot Long",
        session_type      = "Sweet Spot",
        zone_focus        = ["Z3 Tempo", "Z4 Threshold"],
        tss_min           = 90,
        tss_max           = 115,
        duration_min_h    = 1.75,
        duration_max_h    = 2.25,
        description       = (
            "2x20 min at 88-93% FTP, 5 min recovery. "
            "Core build-phase workout. Ensure TSB > -20 before attempting."
        ),
        applicable_phases = ["base", "build"],
        intensity         = "moderate",
        steps             = [
            WorkoutStep("Warm up",    "warmup",   900,  0.45, 0.54, None, 1),
            WorkoutStep("Sweet Spot", "work",     1200, 0.88, 0.93, 90,   2),
            WorkoutStep("Recovery",   "recovery", 300,  0.45, 0.54, 80,   1),
            WorkoutStep("Cool down",  "cooldown", 600,  0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Taper Activation",
        session_type      = "Activation",
        zone_focus        = ["Z2 Endurance", "Z4 Threshold"],
        tss_min           = 40,
        tss_max           = 60,
        duration_min_h    = 1.0,
        duration_max_h    = 1.5,
        description       = (
            "Warm-up + 4x30 s at 110-115% FTP with 90 s recovery + cool-down. "
            "Maintains neuromuscular activation during taper without fatigue."
        ),
        applicable_phases = ["taper"],
        intensity         = "moderate",
        steps             = [
            WorkoutStep("Warm up",    "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("Activation", "work",     30,  1.10, 1.15, 100,  4),
            WorkoutStep("Recovery",   "recovery", 90,  0.45, 0.54, 80,   1),
            WorkoutStep("Cool down",  "cooldown", 900, 0.40, 0.50, None, 1),
        ],
    ),

    # -- High intensity ------------------------------------------------------

    Workout(
        name              = "2x20 Threshold",
        session_type      = "Threshold",
        zone_focus        = ["Z4 Threshold"],
        tss_min           = 85,
        tss_max           = 105,
        duration_min_h    = 1.25,
        duration_max_h    = 1.75,
        description       = (
            "2x20 min at 95-105% FTP, 5 min recovery. "
            "Classic threshold workout -- drives lactate threshold upward. "
            "Aim for even splits. Cadence 85-92 rpm."
        ),
        applicable_phases = ["build", "peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900,  0.45, 0.54, None, 1),
            WorkoutStep("Threshold", "work",     1200, 0.95, 1.05, 88,   2),
            WorkoutStep("Recovery",  "recovery", 300,  0.45, 0.54, 80,   1),
            WorkoutStep("Cool down", "cooldown", 600,  0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "4x8 Threshold Blocks",
        session_type      = "Threshold Intervals",
        zone_focus        = ["Z4 Threshold"],
        tss_min           = 90,
        tss_max           = 115,
        duration_min_h    = 1.5,
        duration_max_h    = 2.0,
        description       = (
            "4x8 min at 98-106% FTP, 4 min recovery. "
            "Shorter intervals allow slightly higher power. "
            "Recovery should be active (50-55% FTP), not stopped."
        ),
        applicable_phases = ["build", "peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("Threshold", "work",     480, 0.98, 1.06, 88,   4),
            WorkoutStep("Recovery",  "recovery", 240, 0.50, 0.55, 80,   1),
            WorkoutStep("Cool down", "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Over-Unders",
        session_type      = "Over-Under Intervals",
        zone_focus        = ["Z4 Threshold", "Z5 VO2max"],
        tss_min           = 90,
        tss_max           = 120,
        duration_min_h    = 1.5,
        duration_max_h    = 2.0,
        description       = (
            "3 sets of 5x (2 min at 85% FTP / 1 min at 110% FTP), 5 min between sets. "
            "Trains lactate clearance -- the overshoot forces the body to process "
            "lactate accumulated below threshold, simulating race surges."
        ),
        applicable_phases = ["build", "peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("Under",     "work",     120, 0.85, 0.90, 88,   5),
            WorkoutStep("Over",      "work",     60,  1.05, 1.10, 90,   1),
            WorkoutStep("Set rest",  "recovery", 300, 0.45, 0.54, 80,   1),
            WorkoutStep("Cool down", "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "5x4 VO2max",
        session_type      = "VO2max Intervals",
        zone_focus        = ["Z5 VO2max"],
        tss_min           = 90,
        tss_max           = 115,
        duration_min_h    = 1.25,
        duration_max_h    = 1.75,
        description       = (
            "5x4 min at 110-120% FTP, 4 min recovery. "
            "Targets VO2max -- the ceiling on aerobic power. "
            "Cadence 95-105 rpm. Expect respiratory distress in the final 90 s."
        ),
        applicable_phases = ["build", "peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",         "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("VO2max Interval", "work",     240, 1.10, 1.20, 100,  5),
            WorkoutStep("Recovery",        "recovery", 240, 0.45, 0.54, 80,   1),
            WorkoutStep("Cool down",       "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "8x2 Short VO2max",
        session_type      = "Short Power Intervals",
        zone_focus        = ["Z5 VO2max", "Z6 Anaerobic"],
        tss_min           = 80,
        tss_max           = 105,
        duration_min_h    = 1.25,
        duration_max_h    = 1.75,
        description       = (
            "8x2 min at 115-125% FTP, 3 min recovery. "
            "Develops anaerobic capacity and VO2max simultaneously. "
            "Good for riders who struggle to maintain 4-min efforts."
        ),
        applicable_phases = ["build", "peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("VO2max",    "work",     120, 1.15, 1.25, 100,  8),
            WorkoutStep("Recovery",  "recovery", 180, 0.45, 0.54, 80,   1),
            WorkoutStep("Cool down", "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "30/30 Microbursts",
        session_type      = "Neuromuscular Power",
        zone_focus        = ["Z6 Anaerobic", "Z5 VO2max"],
        tss_min           = 75,
        tss_max           = 100,
        duration_min_h    = 1.0,
        duration_max_h    = 1.5,
        description       = (
            "20x (30 s at 130-140% FTP / 30 s at 50% FTP). "
            "Builds sprint repeatability and anaerobic capacity. "
            "Lower fatigue cost than sustained VO2max work."
        ),
        applicable_phases = ["peak"],
        intensity         = "high",
        steps             = [
            WorkoutStep("Warm up",   "warmup",   900, 0.45, 0.54, None, 1),
            WorkoutStep("Burst",     "work",     30,  1.30, 1.40, 110,  20),
            WorkoutStep("Float",     "recovery", 30,  0.45, 0.54, 90,   1),
            WorkoutStep("Cool down", "cooldown", 600, 0.40, 0.50, None, 1),
        ],
    ),

    Workout(
        name              = "Race-Day Opener",
        session_type      = "Activation",
        zone_focus        = ["Z2 Endurance", "Z5 VO2max"],
        tss_min           = 30,
        tss_max           = 45,
        duration_min_h    = 0.75,
        duration_max_h    = 1.25,
        description       = (
            "20 min easy + 3x1 min at 110% FTP with 5 min easy between + 15 min cool-down. "
            "Opens the legs and primes the neuromuscular system without adding fatigue."
        ),
        applicable_phases = ["taper"],
        intensity         = "moderate",
        steps             = [
            WorkoutStep("Warm up",    "warmup",   1200, 0.45, 0.54, None, 1),
            WorkoutStep("Activation", "work",     60,   1.05, 1.10, 100,  3),
            WorkoutStep("Easy spin",  "recovery", 300,  0.45, 0.54, 85,   1),
            WorkoutStep("Cool down",  "cooldown", 900,  0.40, 0.50, None, 1),
        ],
    ),
]
