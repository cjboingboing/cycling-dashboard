"""
garmin_push.py
--------------
Push structured workouts to Garmin Connect via garth (unofficial API).

Garmin Connect workout endpoints:
  POST /workout-service/workout           → create workout → {workoutId}
  POST /workout-service/schedule/{id}    → schedule on date → body {"date": "YYYY-MM-DD"}
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

try:
    import garth as _garth
    _GARTH_AVAILABLE = True
except ImportError:
    _GARTH_AVAILABLE = False

from src.recommender.workout_library import Workout, WorkoutStep


_SPORT_TYPE = {"sportTypeId": 2, "sportTypeKey": "cycling"}

_STEP_TYPES = {
    "warmup":   {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
    "work":     {"stepTypeId": 3, "stepTypeKey": "interval"},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery"},
    "rest":     {"stepTypeId": 5, "stepTypeKey": "rest"},
}

_NO_TARGET  = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
_PWR_TARGET = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "power.zone"}


def is_available() -> bool:
    return _GARTH_AVAILABLE


def authenticate(token_dir: str = "~/.garth") -> None:
    """Login using stored tokens or GARMIN_EMAIL / GARMIN_PASSWORD from env."""
    if not _GARTH_AVAILABLE:
        raise ImportError("garth is required: pip install garth")
    path = Path(token_dir).expanduser()
    if path.exists():
        _garth.resume(str(path))
    else:
        email    = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "Set GARMIN_EMAIL and GARMIN_PASSWORD in .env for first-time auth."
            )
        _garth.login(email, password)
        _garth.save(str(path))


def push_workout(
    workout:       Workout,
    ftp:           int,
    schedule_date: date | None = None,
    token_dir:     str = "~/.garth",
) -> str:
    """
    Create a structured workout on Garmin Connect and optionally schedule it.

    Returns the Garmin workout ID string.
    """
    authenticate(token_dir)
    payload  = _build_payload(workout, ftp)
    response = _garth.connectapi("/workout-service/workout", method="POST", json=payload)
    workout_id = str(response["workoutId"])

    if schedule_date is not None:
        _garth.connectapi(
            f"/workout-service/schedule/{workout_id}",
            method="POST",
            json={"date": schedule_date.isoformat()},
        )

    return workout_id


# ── Payload builders ──────────────────────────────────────────────────────────

def _build_payload(workout: Workout, ftp: int) -> dict:
    return {
        "workoutName":     workout.name,
        "description":     workout.description[:250],
        "sportType":       _SPORT_TYPE,
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType":    _SPORT_TYPE,
            "workoutSteps": _build_steps(workout.steps, ftp),
        }],
    }


def _build_steps(steps: list[WorkoutStep], ftp: int) -> list[dict]:
    """Convert WorkoutStep list → Garmin API steps, grouping repeat intervals."""
    result, order, i = [], 1, 0
    while i < len(steps):
        s = steps[i]
        if s.repeat_count > 1 and i + 1 < len(steps):
            rec = steps[i + 1]
            result.append({
                "type":               "RepeatGroupDTO",
                "stepOrder":          order,
                "numberOfIterations": s.repeat_count,
                "smartRepeat":        False,
                "workoutSteps": [
                    _build_single(s,   1, ftp),
                    _build_single(rec, 2, ftp),
                ],
            })
            i += 2
        else:
            result.append(_build_single(s, order, ftp))
            i += 1
        order += 1
    return result


def _build_single(step: WorkoutStep, order: int, ftp: int) -> dict:
    if step.duration_s is not None:
        end_cond  = {"conditionTypeId": 2, "conditionTypeKey": "time"}
        end_value = step.duration_s * 1000   # ms
    else:
        end_cond  = {"conditionTypeId": 1, "conditionTypeKey": "lapButton"}
        end_value = None

    has_power = step.power_target_low is not None and step.power_target_high is not None
    out = {
        "stepOrder":    order,
        "stepType":     _STEP_TYPES.get(step.step_type, _STEP_TYPES["work"]),
        "endCondition": end_cond,
        "targetType":   _PWR_TARGET if has_power else _NO_TARGET,
    }
    if end_value is not None:
        out["endConditionValue"] = end_value
    if has_power:
        out["targetValueOne"] = round(step.power_target_low  * ftp)
        out["targetValueTwo"] = round(step.power_target_high * ftp)

    return out
