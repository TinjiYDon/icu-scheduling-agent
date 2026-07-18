"""Gymnasium-compatible ICU bed-assignment environment for PPO.

The environment makes one decision per patient.  An action selects a bed by
zero-based index; the last action means that the patient keeps waiting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import gymnasium as gym
import numpy as np
from gymnasium import spaces


@dataclass(frozen=True)
class Patient:
    stay_id: int
    priority_weight: float
    sofa_total: float = 0.0
    wait_hours: float = 0.0
    preferred_zone: str = "UNK"
    needs_isolation: bool = False
    needs_ventilator: bool = False


@dataclass(frozen=True)
class Bed:
    bed_id: int
    zone: str = "REG"
    is_isolation: bool = False
    has_ventilator: bool = False


DEFAULT_REWARD_WEIGHTS = {
    "wait": 10.0,
    "overload": 1.0,
    "balance": 0.1,
    "zone_mismatch": 0.5,
}


class ICUEnv(gym.Env):
    """Sequential, masked bed-assignment environment.

    Observation layout:
      current patient (7 values), every bed (occupied/iso/vent/zone = 4),
      then progress and current utilization (2 values).
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        patients: Sequence[Patient],
        beds: Sequence[Bed],
        reward_weights: Mapping[str, float] | None = None,
        *,
        invalid_action_penalty: float = 10.0,
        wait_action_penalty: float = 1.0,
        ventilator_capacity: int | None = None,
        episode_size: int | None = None,
        shuffle_on_reset: bool = False,
    ) -> None:
        super().__init__()
        if not beds:
            raise ValueError("ICUEnv requires at least one bed")
        self._patient_pool = list(patients)
        requested_episode_size = (
            len(self._patient_pool) if episode_size is None else int(episode_size)
        )
        self.episode_size = min(requested_episode_size, len(self._patient_pool))
        if self.episode_size < 0:
            raise ValueError("episode_size must be non-negative")
        self.shuffle_on_reset = shuffle_on_reset
        self.patients = self._patient_pool[: self.episode_size]
        self.beds = list(beds)
        self.reward_weights = dict(DEFAULT_REWARD_WEIGHTS)
        if reward_weights:
            unknown = set(reward_weights) - set(self.reward_weights)
            if unknown:
                raise ValueError(f"unknown reward weight(s): {', '.join(sorted(unknown))}")
            self.reward_weights.update({k: float(v) for k, v in reward_weights.items()})
        if any(v < 0 or not np.isfinite(v) for v in self.reward_weights.values()):
            raise ValueError("reward weights must be finite and non-negative")
        self.invalid_action_penalty = float(invalid_action_penalty)
        self.wait_action_penalty = float(wait_action_penalty)
        self.ventilator_capacity = (
            int(ventilator_capacity)
            if ventilator_capacity is not None
            else sum(bed.has_ventilator for bed in self.beds)
        )
        if (
            self.invalid_action_penalty < 0
            or self.wait_action_penalty < 0
            or not np.isfinite(self.invalid_action_penalty)
            or not np.isfinite(self.wait_action_penalty)
        ):
            raise ValueError("action penalties must be finite and non-negative")
        if self.ventilator_capacity < 0:
            raise ValueError("ventilator_capacity must be non-negative")
        self.wait_action = len(self.beds)
        self.action_space = spaces.Discrete(len(self.beds) + 1)
        observation_size = 7 + 4 * len(self.beds) + 2
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(observation_size,), dtype=np.float32
        )
        self._patient_index = 0
        self._occupants: list[int | None] = [None] * len(self.beds)
        self._ventilator_users = 0
        self.assignments: list[dict] = []

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if self.shuffle_on_reset and self._patient_pool:
            indices = self.np_random.permutation(len(self._patient_pool))[
                : self.episode_size
            ]
            self.patients = [self._patient_pool[int(index)] for index in indices]
        else:
            self.patients = self._patient_pool[: self.episode_size]
        self._patient_index = 0
        self._occupants = [None] * len(self.beds)
        self._ventilator_users = 0
        self.assignments = []
        return self._observation(), {"action_mask": self.action_masks()}

    def action_masks(self) -> np.ndarray:
        """Return the mask expected by sb3-contrib MaskablePPO."""
        mask = np.zeros(self.action_space.n, dtype=bool)
        mask[self.wait_action] = True
        patient = self.current_patient
        if patient is None:
            return mask
        for index, bed in enumerate(self.beds):
            mask[index] = self._bed_is_valid(patient, bed, index)
        return mask

    @property
    def current_patient(self) -> Patient | None:
        if self._patient_index >= len(self.patients):
            return None
        return self.patients[self._patient_index]

    def step(self, action: int):
        if self.current_patient is None:
            raise RuntimeError("episode is finished; call reset()")
        if not self.action_space.contains(action):
            raise ValueError(f"action {action} is outside the action space")

        patient = self.current_patient
        components = {
            "priority": 0.0,
            "wait": 0.0,
            "overload": 0.0,
            "balance": 0.0,
            "zone_mismatch": 0.0,
            "invalid": 0.0,
        }
        valid_mask = self.action_masks()
        if not valid_mask[action]:
            components["invalid"] = -self.invalid_action_penalty
        elif action == self.wait_action:
            components["wait"] = -self.wait_action_penalty * (
                1.0 + patient.wait_hours / 24.0
            ) * patient.priority_weight
        else:
            bed = self.beds[action]
            self._occupants[action] = patient.stay_id
            if patient.needs_ventilator:
                self._ventilator_users += 1
            components["priority"] = (
                self.reward_weights["wait"] * patient.priority_weight
            )
            if patient.sofa_total >= 10 and not (bed.is_isolation or bed.has_ventilator):
                components["overload"] = -self.reward_weights["overload"] * (
                    patient.sofa_total / 24.0
                )
            if patient.preferred_zone not in ("", "UNK", bed.zone):
                components["zone_mismatch"] = -self.reward_weights["zone_mismatch"]
            components["balance"] = (
                -self.reward_weights["balance"] * self._balance_deviation()
            )
            self.assignments.append(
                {"stay_id": patient.stay_id, "bed_id": bed.bed_id, "zone": bed.zone}
            )

        reward = float(sum(components.values()))
        self._patient_index += 1
        terminated = self._patient_index >= len(self.patients)
        info = {
            "reward_components": components,
            "action_mask": self.action_masks(),
            "assigned": len(self.assignments),
        }
        return self._observation(), reward, terminated, False, info

    def _bed_is_valid(self, patient: Patient, bed: Bed, index: int) -> bool:
        if self._occupants[index] is not None:
            return False
        if patient.needs_isolation != bed.is_isolation:
            return False
        if patient.needs_ventilator:
            if not bed.has_ventilator:
                return False
            if self._ventilator_users >= self.ventilator_capacity:
                return False
        return True

    def _balance_deviation(self) -> float:
        zone_loads: dict[str, int] = {}
        for index, occupant in enumerate(self._occupants):
            if occupant is not None:
                zone = self.beds[index].zone
                zone_loads[zone] = zone_loads.get(zone, 0) + 1
        all_zones = {bed.zone for bed in self.beds}
        loads = [zone_loads.get(zone, 0) for zone in all_zones]
        return float(max(loads) - min(loads)) if loads else 0.0

    def _observation(self) -> np.ndarray:
        patient = self.current_patient
        if patient is None:
            patient_values = [0.0] * 7
        else:
            patient_values = [
                min(patient.priority_weight / 10.0, 1.0),
                min(patient.sofa_total / 24.0, 1.0),
                min(patient.wait_hours / 48.0, 1.0),
                float(patient.needs_isolation),
                float(patient.needs_ventilator),
                self._zone_value(patient.preferred_zone),
                1.0,
            ]
        bed_values: list[float] = []
        for index, bed in enumerate(self.beds):
            bed_values.extend(
                [
                    float(self._occupants[index] is not None),
                    float(bed.is_isolation),
                    float(bed.has_ventilator),
                    self._zone_value(bed.zone),
                ]
            )
        total_patients = max(len(self.patients), 1)
        system_values = [
            min(self._patient_index / total_patients, 1.0),
            sum(o is not None for o in self._occupants) / len(self.beds),
        ]
        return np.asarray(patient_values + bed_values + system_values, dtype=np.float32)

    def _zone_value(self, zone: str) -> float:
        zones = sorted({bed.zone for bed in self.beds} | {"UNK"})
        return zones.index(zone) / max(len(zones) - 1, 1) if zone in zones else 0.0
