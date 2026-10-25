from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SnapshotSource(str, Enum):
    ADAPTER = "adapter"
    FIXTURE = "fixture"
    SIMULATOR = "simulator"


class VehicleInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vin: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1886, le=2100)
    engine: str | None = None


class DTC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=3, max_length=7)
    description: str | None = None
    status: str = "stored"
    confirmed: bool | None = None
    pending: bool = False
    permanent: bool = False

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class FreezeFrame(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: dict[str, float | int | str | bool | None] = Field(default_factory=dict)


class LivePID(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: float | int | str | bool | None = None
    unit: str | None = None
    available: bool = True


class Readiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complete: bool | None = None
    monitors: dict[str, bool | None] = Field(default_factory=dict)


class VehicleSnapshot(BaseModel):
    """Validated, serializable input boundary for one diagnosis."""

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: SnapshotSource
    vehicle: VehicleInfo = Field(default_factory=VehicleInfo)
    dtcs: list[DTC] = Field(default_factory=list)
    freeze_frame: FreezeFrame | None = None
    live_pids: dict[str, LivePID] = Field(default_factory=dict)
    readiness: Readiness | None = None
    symptoms: list[str] = Field(default_factory=list)
    technician_notes: str | None = None
    expected: dict[str, Any] | None = None

    @field_validator("symptoms")
    @classmethod
    def remove_blank_symptoms(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def redacted(self, *, redact_vin: bool = True) -> "VehicleSnapshot":
        """Return a copy safe to include in an external model prompt."""
        if not redact_vin or self.vehicle.vin is None:
            return self.model_copy(deep=True)
        return self.model_copy(
            deep=True,
            update={
                "vehicle": self.vehicle.model_copy(
                    update={"vin": "[REDACTED]"}
                )
            },
        )

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_json_file(cls, path: str) -> "VehicleSnapshot":
        from pathlib import Path

        return cls.model_validate_json(Path(path).read_text())

    def write_json(self, path: str) -> None:
        from pathlib import Path

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2) + "\n")


class Severity(str, Enum):
    DRIVE_NORMALLY = "drive_normally"
    DRIVE_WITH_CAUTION = "drive_with_caution"
    LIMIT_DRIVING = "limit_driving"
    DO_NOT_DRIVE = "do_not_drive"


class Evidence(BaseModel):
    kind: str
    detail: str
    source: str = "snapshot"


class Cause(BaseModel):
    rank: int
    title: str
    probability: float = Field(ge=0, le=1)
    reasoning: str
    evidence: list[Evidence] = Field(default_factory=list)


class NextTest(BaseModel):
    order: int
    name: str
    expected_if_faulty: str
    expected_if_ok: str


class Diagnosis(BaseModel):
    summary: str
    severity: Severity
    causes: list[Cause] = Field(default_factory=list)
    next_tests: list[NextTest] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    citations: dict[str, str] = Field(default_factory=dict)
