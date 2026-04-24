from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
import copy
import uuid


EventHandler = Callable[[dict[str, Any]], None]


@dataclass
class ImageContext:
    image_id: str
    source_image_path: str
    image_name: str
    frame_index: int = 0
    role_bindings: dict[str, str] = field(default_factory=dict)


@dataclass
class Measurement:
    measurement_id: str
    image_id: str
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    frame_index: int
    geometry_key: str
    summary_text: str
    role: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    order_index: int = 0


@dataclass
class AnalysisRun:
    run_id: str
    image_id: str
    requested_at: str
    analysis_type: str
    input_measurement_ids: list[str] = field(default_factory=list)
    status: str = "requested"
    result_entry_ids: list[str] = field(default_factory=list)


@dataclass
class ResultHistoryEntry:
    entry_id: str
    run_id: str
    image_id: str
    metric: str
    value: float | None
    unit: str
    created_at: str
    measurement_type: str
    target_id: str


@dataclass
class ImageAnalysisGroup:
    group_id: str
    study_id: str
    image_id: str
    entry_ids: list[str] = field(default_factory=list)


@dataclass
class StudySession:
    session_id: str
    name: str
    created_at: str
    image_ids: list[str] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)


@dataclass
class DomainState:
    images: dict[str, ImageContext] = field(default_factory=dict)
    measurements: dict[str, Measurement] = field(default_factory=dict)
    analysis_runs: dict[str, AnalysisRun] = field(default_factory=dict)
    history_entries: dict[str, ResultHistoryEntry] = field(default_factory=dict)
    analysis_groups: dict[str, ImageAnalysisGroup] = field(default_factory=dict)
    sessions: dict[str, StudySession] = field(default_factory=dict)
    analysis_last_run: dict[str, dict[str, Any]] = field(default_factory=dict)
    history_payloads: list[dict[str, Any]] = field(default_factory=list)
    selected_image_id: str | None = None
    selected_measurement_ids: list[str] = field(default_factory=list)
    measurement_order_counter: int = 0


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event_payload = {"event_type": event_type, **payload}
        for handler in self._handlers.get(event_type, []):
            handler(event_payload)


class DomainStore:
    def __init__(self) -> None:
        self.state = DomainState()
        self.events = EventDispatcher()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_image_context(self, source_image_path: str, image_name: str, frame_index: int = 0) -> str:
        image_id = str(uuid.uuid4())
        self.state.images[image_id] = ImageContext(
            image_id=image_id,
            source_image_path=source_image_path,
            image_name=image_name,
            frame_index=frame_index,
        )
        if self.state.selected_image_id is None:
            self.state.selected_image_id = image_id
        return image_id

    def add_measurement(
        self,
        image_id: str,
        kind: str,
        start: tuple[float, float],
        end: tuple[float, float],
        frame_index: int,
        geometry_key: str,
        summary_text: str,
        role: str | None = None,
        meta: dict[str, Any] | None = None,
        measurement_id: str | None = None,
    ) -> str:
        measurement_id = measurement_id or str(uuid.uuid4())
        self.state.measurement_order_counter += 1
        created_at = self._now()
        self.state.measurements[measurement_id] = Measurement(
            measurement_id=measurement_id,
            image_id=image_id,
            kind=kind,
            start=(float(start[0]), float(start[1])),
            end=(float(end[0]), float(end[1])),
            frame_index=frame_index,
            geometry_key=geometry_key,
            summary_text=summary_text,
            role=role,
            meta=meta or {},
            created_at=created_at,
            order_index=self.state.measurement_order_counter,
        )
        self.events.publish(
            "measurement_added",
            {
                "measurement_id": measurement_id,
                "image_id": image_id,
                "kind": kind,
                "change": "created",
            },
        )
        return measurement_id

    def update_measurement(self, measurement_id: str, **updates: Any) -> None:
        measurement = self.state.measurements[measurement_id]
        for key, value in updates.items():
            setattr(measurement, key, value)
        self.events.publish(
            "measurement_updated",
            {
                "measurement_id": measurement_id,
                "image_id": measurement.image_id,
                "kind": measurement.kind,
                "change": "updated",
            },
        )

    def delete_measurement(self, measurement_id: str) -> None:
        measurement = self.state.measurements.pop(measurement_id)
        if measurement_id in self.state.selected_measurement_ids:
            self.state.selected_measurement_ids = [
                item for item in self.state.selected_measurement_ids if item != measurement_id
            ]
        self.events.publish(
            "measurement_deleted",
            {
                "measurement_id": measurement_id,
                "image_id": measurement.image_id,
                "kind": measurement.kind,
                "change": "deleted",
            },
        )

    def set_selection(self, image_id: str | None, measurement_ids: list[str]) -> None:
        self.state.selected_image_id = image_id
        self.state.selected_measurement_ids = list(measurement_ids)
        self.events.publish(
            "selection_changed",
            {
                "image_id": image_id,
                "selected_measurement_ids": list(measurement_ids),
                "change": "selection",
            },
        )

    def set_frame(self, image_id: str, frame_index: int) -> None:
        self.state.images[image_id].frame_index = frame_index
        self.events.publish(
            "frame_changed",
            {
                "image_id": image_id,
                "frame_index": frame_index,
                "change": "frame",
            },
        )

    def set_role(self, measurement_id: str, role: str | None) -> None:
        measurement = self.state.measurements[measurement_id]
        measurement.role = role
        self.events.publish(
            "role_changed",
            {
                "measurement_id": measurement_id,
                "image_id": measurement.image_id,
                "role": role,
                "change": "role",
            },
        )

    def request_analysis(self, image_id: str, analysis_type: str, input_measurement_ids: list[str]) -> str:
        run_id = str(uuid.uuid4())
        self.state.analysis_runs[run_id] = AnalysisRun(
            run_id=run_id,
            image_id=image_id,
            analysis_type=analysis_type,
            input_measurement_ids=list(input_measurement_ids),
            requested_at=self._now(),
        )
        self.events.publish(
            "analysis_requested",
            {
                "run_id": run_id,
                "image_id": image_id,
                "analysis_type": analysis_type,
                "input_measurement_ids": list(input_measurement_ids),
            },
        )
        return run_id

    def complete_analysis(self, run_id: str, results: list[dict[str, Any]]) -> list[str]:
        run = self.state.analysis_runs[run_id]
        run.status = "completed"
        entry_ids: list[str] = []
        for result in results:
            entry_id = str(uuid.uuid4())
            entry_ids.append(entry_id)
            self.state.history_entries[entry_id] = ResultHistoryEntry(
                entry_id=entry_id,
                run_id=run_id,
                image_id=run.image_id,
                metric=result["metric"],
                value=result.get("value"),
                unit=result.get("unit", ""),
                created_at=self._now(),
                measurement_type=result.get("measurement_type", run.analysis_type),
                target_id=result.get("target_id", ""),
            )
        run.result_entry_ids = entry_ids
        self.events.publish(
            "analysis_completed",
            {
                "run_id": run_id,
                "image_id": run.image_id,
                "result_entry_ids": list(entry_ids),
                "analysis_type": run.analysis_type,
            },
        )
        return entry_ids

    def save_session(self, session_id: str, name: str) -> dict[str, Any]:
        timestamp = self._now()
        snapshot = self.snapshot(timestamp)
        self.state.sessions[session_id] = StudySession(
            session_id=session_id,
            name=name,
            created_at=timestamp,
            image_ids=list(self.state.images.keys()),
            group_ids=list(self.state.analysis_groups.keys()),
        )
        self.events.publish(
            "session_saved",
            {
                "session_id": session_id,
                "snapshot_timestamp": timestamp,
                "change": "saved",
            },
        )
        return snapshot

    def load_session(self, snapshot: dict[str, Any]) -> None:
        self.state = copy.deepcopy(snapshot["state"])
        self.events.publish(
            "session_loaded",
            {
                "session_id": snapshot.get("session_id", ""),
                "snapshot_timestamp": snapshot["snapshot_timestamp"],
                "change": "loaded",
            },
        )

    def snapshot(self, timestamp: str | None = None) -> dict[str, Any]:
        return {
            "snapshot_timestamp": timestamp or self._now(),
            "state": copy.deepcopy(self.state),
        }

    def set_analysis_last_run(self, key: str, payload: dict[str, Any]) -> None:
        self.state.analysis_last_run[key] = copy.deepcopy(payload)

    def clear_analysis_last_run(self) -> None:
        self.state.analysis_last_run = {}

    def select_analysis_last_run(self, key: str) -> dict[str, Any]:
        return copy.deepcopy(self.state.analysis_last_run.get(key) or {})

    def select_all_analysis_last_run(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self.state.analysis_last_run)

    def append_history_payload(self, payload: dict[str, Any]) -> None:
        self.state.history_payloads.append(copy.deepcopy(payload))

    def replace_history_payloads(self, payloads: list[dict[str, Any]]) -> None:
        self.state.history_payloads = [copy.deepcopy(item) for item in payloads]

    def remove_history_payload_indices(self, indices: list[int]) -> None:
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self.state.history_payloads):
                self.state.history_payloads.pop(index)

    def clear_history_payloads(self) -> None:
        self.state.history_payloads.clear()

    def select_history_payloads(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(item) for item in self.state.history_payloads]

    # selectors
    def select_active_image(self) -> ImageContext | None:
        image_id = self.state.selected_image_id
        if image_id is None:
            return None
        return self.state.images.get(image_id)

    def select_measurements_for_image(self, image_id: str, frame_index: int | None = None) -> list[Measurement]:
        rows = [
            measurement
            for measurement in self.state.measurements.values()
            if measurement.image_id == image_id and (frame_index is None or measurement.frame_index == frame_index)
        ]
        return sorted(rows, key=lambda row: (int(row.order_index), str(row.created_at), str(row.measurement_id)))

    def select_measurements_by_role(self, image_id: str, role: str) -> list[Measurement]:
        return [
            measurement
            for measurement in self.select_measurements_for_image(image_id)
            if measurement.role == role
        ]

    def select_measurement_ids_for_image(self, image_id: str, frame_index: int | None = None) -> list[str]:
        return [
            item.measurement_id
            for item in self.select_measurements_for_image(image_id, frame_index=frame_index)
        ]

    def select_analysis_inputs(self, image_id: str, frame_index: int) -> dict[str, list[str]]:
        current_frame_measurements = self.select_measurements_for_image(image_id, frame_index)
        role_map: dict[str, list[str]] = {}
        for measurement in current_frame_measurements:
            key = measurement.role or "unassigned"
            role_map.setdefault(key, []).append(measurement.measurement_id)
        return role_map

    def select_history_entries(self, image_id: str | None = None, run_id: str | None = None) -> list[ResultHistoryEntry]:
        entries = list(self.state.history_entries.values())
        if image_id is not None:
            entries = [entry for entry in entries if entry.image_id == image_id]
        if run_id is not None:
            entries = [entry for entry in entries if entry.run_id == run_id]
        return entries

    def select_analysis_groups(self, study_id: str | None = None) -> list[ImageAnalysisGroup]:
        groups = list(self.state.analysis_groups.values())
        if study_id is not None:
            groups = [group for group in groups if group.study_id == study_id]
        return groups

    def select_study_sessions(self) -> list[StudySession]:
        return list(self.state.sessions.values())
