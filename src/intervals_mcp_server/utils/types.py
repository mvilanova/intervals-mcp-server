from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Union
from enum import Enum
import json


__all__ = [
    'Option',
    'WorkoutTarget',
    'HrTarget',
    'Intensity',
    'PaceUnits',
    'ValueUnits',
    'Value',
    'Step',
    'SportSettings',
    'WorkoutDoc'
]


class Option(Enum):
    CATEGORY = "category"
    POOL_LENGTH = "pool_length"
    POWER = "power"


class WorkoutTarget(Enum):
    AUTO = "AUTO"
    POWER = "POWER"
    HR = "HR"
    PACE = "PACE"


class HrTarget(Enum):
    LAP = "lap"
    INSTANT = "1s"
    THREE_SECOND = "3s"
    TEN_SECOND = "10s"
    THIRTY_SECOND = "30s"
    

class Intensity(Enum):
    ACTIVE = "active"
    REST = "rest"
    WARMUP = "warmup"
    COOLDOWN = "cooldown"
    RECOVERY = "recovery"
    INTERVAL = "interval"
    OTHER = "other"


class PaceUnits(Enum):
    SECS_100M = "SECS_100M"
    SECS_100Y = "SECS_100Y"
    MINS_KM = "MINS_KM"
    MINS_MILE = "MINS_MILE"
    SECS_500M = "SECS_500M"


class ValueUnits(Enum):
    PERCENT_MMP = "%mmp"
    PERCENT_HR = "%hr"
    PERCENT_LTHR = "%lthr"
    PERCENT_PACE = "%pace"
    POWER_ZONE = "power_zone"
    HR_ZONE = "hr_zone"
    PACE_ZONE = "pace_zone"
    WATTS = "w"
    PERCENT_FTP = "%ftp"
    CADENCE = "cadence"


def float_to_str(value: float) -> str:
    """Format the value without decimals if it's a whole number."""
    return str(int(value)) if value.is_integer() else str(value)


@dataclass
class Value:
    value: Optional[float] = None
    start: Optional[float] = None
    end: Optional[float] = None
    units: Optional[ValueUnits] = None
    target: Optional[HrTarget] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Value instance to dictionary for JSON serialization."""
        data = {}
        if self.value is not None:
            data['value'] = self.value
        if self.start is not None:
            data['start'] = self.start
        if self.end is not None:
            data['end'] = self.end
        if self.units is not None:
            data['units'] = self.units.value
        if self.target is not None:
            data['target'] = self.target.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Value':
        """Create Value instance from dictionary."""
        kwargs = {}
        if 'value' in data:
            kwargs['value'] = data['value']
        if 'start' in data:
            kwargs['start'] = data['start']
        if 'end' in data:
            kwargs['end'] = data['end']
        if 'units' in data:
            kwargs['units'] = ValueUnits(data['units'])
        if 'target' in data:
            kwargs['target'] = HrTarget(data['target'])
        return cls(**kwargs)

    def to_json(self) -> str:
        """Convert Value instance to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'Value':
        """Create Value instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def _format_value(self, value: float) -> str:
        if self.units in [ValueUnits.PERCENT_HR, ValueUnits.PERCENT_MMP, ValueUnits.PERCENT_LTHR, ValueUnits.PERCENT_PACE, ValueUnits.PERCENT_FTP]:
            return f"{float_to_str(value)}%"
        elif self.units in [ValueUnits.POWER_ZONE, ValueUnits.HR_ZONE, ValueUnits.PACE_ZONE]:
            return f"Z{float_to_str(value)}"
        elif self.units in [ValueUnits.WATTS]:
            return f"{float_to_str(value)}W"
        elif self.units in [ValueUnits.CADENCE]:
            return f"{float_to_str(value)}rpm"
        return float_to_str(value)

    def _format_units(self) -> str:
        if self.units in [ValueUnits.PERCENT_HR, ValueUnits.HR_ZONE]:
            return "HR"
        elif self.units in [ValueUnits.PERCENT_MMP]:
            return "MMP"
        elif self.units in [ValueUnits.PERCENT_LTHR]:
            return "LTHR"
        elif self.units in [ValueUnits.PERCENT_PACE, ValueUnits.PACE_ZONE]:
            return "Pace"
        elif self.units in [ValueUnits.PERCENT_FTP]:
            return "ftp"
        elif self.units in [ValueUnits.POWER_ZONE]:
            return "W"
        elif self.units in [ValueUnits.CADENCE]:
            return "Cadence"
        return ""

    def __str__(self) -> str:
        val = ""
        if self.start is not None and self.end is not None:
            val += f"{self._format_value(self.start)}-{self._format_value(self.end)} "
        if self.value is not None:
            val += f"{self._format_value(self.value)} "
        if self.units is not None:
            val += f"{self._format_units()} "
        if self.target is not None:
            val += f"hr={self.target.value} "
        return val.strip()


@dataclass
class Step:
    text: Optional[str] = None
    text_locale: Optional[Dict[str, str]] = None
    duration: Optional[int] = None
    distance: Optional[float] = None
    until_lap_press: Optional[bool] = None
    reps: Optional[int] = None
    warmup: Optional[bool] = None
    cooldown: Optional[bool] = None
    intensity: Optional[Intensity] = None
    steps: Optional[List['Step']] = None
    ramp: Optional[bool] = None
    freeride: Optional[bool] = None
    maxeffort: Optional[bool] = None
    power: Optional[Value] = None
    hr: Optional[Value] = None
    pace: Optional[Value] = None
    cadence: Optional[Value] = None
    hidepower: Optional[bool] = None
    # these are filled in with actual watts, bpm etc. when resolve=true parameter is supplied to the endpoint
    _power: Optional[Value] = None
    _hr: Optional[Value] = None
    _pace: Optional[Value] = None
    _distance: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Step instance to dictionary for JSON serialization."""
        data = {}
        if self.text is not None:
            data['text'] = self.text
        if self.text_locale is not None:
            data['text_locale'] = self.text_locale
        if self.duration is not None:
            data['duration'] = self.duration
        if self.distance is not None:
            data['distance'] = self.distance
        if self.until_lap_press is not None:
            data['until_lap_press'] = self.until_lap_press
        if self.reps is not None:
            data['reps'] = self.reps
        if self.warmup is not None:
            data['warmup'] = self.warmup
        if self.cooldown is not None:
            data['cooldown'] = self.cooldown
        if self.intensity is not None:
            data['intensity'] = self.intensity.value
        if self.steps is not None:
            data['steps'] = [step.to_dict() for step in self.steps]
        if self.ramp is not None:
            data['ramp'] = self.ramp
        if self.freeride is not None:
            data['freeride'] = self.freeride
        if self.maxeffort is not None:
            data['maxeffort'] = self.maxeffort
        if self.power is not None:
            data['power'] = self.power.to_dict()
        if self.hr is not None:
            data['hr'] = self.hr.to_dict()
        if self.pace is not None:
            data['pace'] = self.pace.to_dict()
        if self.cadence is not None:
            data['cadence'] = self.cadence.to_dict()
        if self.hidepower is not None:
            data['hidepower'] = self.hidepower
        if self._power is not None:
            data['_power'] = self._power.to_dict()
        if self._hr is not None:
            data['_hr'] = self._hr.to_dict()
        if self._pace is not None:
            data['_pace'] = self._pace.to_dict()
        if self._distance is not None:
            data['_distance'] = self._distance
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Step':
        """Create Step instance from dictionary."""
        kwargs = {}
        if 'text' in data:
            kwargs['text'] = data['text']
        if 'text_locale' in data:
            kwargs['text_locale'] = data['text_locale']
        if 'duration' in data:
            kwargs['duration'] = data['duration']
        if 'distance' in data:
            kwargs['distance'] = data['distance']
        if 'until_lap_press' in data:
            kwargs['until_lap_press'] = data['until_lap_press']
        if 'reps' in data:
            kwargs['reps'] = data['reps']
        if 'warmup' in data:
            kwargs['warmup'] = data['warmup']
        if 'cooldown' in data:
            kwargs['cooldown'] = data['cooldown']
        if 'intensity' in data:
            kwargs['intensity'] = Intensity(data['intensity'])
        if 'steps' in data:
            kwargs['steps'] = [cls.from_dict(step) for step in data['steps']]
        if 'ramp' in data:
            kwargs['ramp'] = data['ramp']
        if 'freeride' in data:
            kwargs['freeride'] = data['freeride']
        if 'maxeffort' in data:
            kwargs['maxeffort'] = data['maxeffort']
        if 'power' in data:
            kwargs['power'] = Value.from_dict(data['power'])
        if 'hr' in data:
            kwargs['hr'] = Value.from_dict(data['hr'])
        if 'pace' in data:
            kwargs['pace'] = Value.from_dict(data['pace'])
        if 'cadence' in data:
            kwargs['cadence'] = Value.from_dict(data['cadence'])
        if 'hidepower' in data:
            kwargs['hidepower'] = data['hidepower']
        if '_power' in data:
            kwargs['_power'] = Value.from_dict(data['_power'])
        if '_hr' in data:
            kwargs['_hr'] = Value.from_dict(data['_hr'])
        if '_pace' in data:
            kwargs['_pace'] = Value.from_dict(data['_pace'])
        if '_distance' in data:
            kwargs['_distance'] = data['_distance']
        return cls(**kwargs)

    def to_json(self) -> str:
        """Convert Step instance to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'Step':
        """Create Step instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def _format_duration(self) -> str:
        """Format duration into a human-readable string."""
        if self.duration is None:
            return ""
        remaining_duration = self.duration
        val = ""
        if remaining_duration > 3600:
            val += f"{remaining_duration // 3600}h"
            remaining_duration %= 3600
        if remaining_duration > 100 or remaining_duration == 60:
            val += f"{remaining_duration // 60}m"
            remaining_duration %= 60
        if remaining_duration > 0:
            val += f"{remaining_duration}s"
        return val

    def _format_distance(self) -> str:
        """Format distance into a human-readable string."""
        if self.distance is None:
            return ""
        if self.distance < 1000:
            return f"{float_to_str(self.distance)}mtr"
        return f"{float_to_str(self.distance / 1000)}km"

    def __str__(self, nested: bool = False) -> str:
        val = ""
        if self.reps is not None:
            if nested:
                raise ValueError("Nested steps not supported")
            val += f"\n{self.reps}x "
        else:
            if not nested and self.warmup:
                val += "\nWarmup\n"
            if not nested and self.cooldown:
                val += "\nCooldown\n"

            val += ""
            if self.duration is not None:
                val += f"- {self._format_duration()} "
            elif self.distance is not None:
                val += f"- {self._format_distance()} "

            if self.freeride:
                val += "freeride "
            if self.maxeffort:
                val += "maxeffort "
            if self.ramp:
                val += "ramp "
            if self.hidepower:
                val += "hidepower "
            if self.intensity is not None:
                val += f"intensity={self.intensity.value} "

            if self.power is not None:
                val += f"{self.power} "
            if self.hr is not None:
                val += f"{self.hr} "
            if self.pace is not None:
                val += f"{self.pace} "
            if self.cadence is not None:
                val += f"{self.cadence} "
        if self.text is not None:
            val += f"{self.text} "
        
        if self.reps is not None and self.steps is not None:
            for step in self.steps:
                val += "\n" + step.__str__(nested=True)
            val += "\n"
        elif not nested and (self.warmup or self.cooldown):
            val += "\n"
        return val


@dataclass
class SportSettings:
    # Add fields as needed based on the actual SportSettings class
    pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert SportSettings instance to dictionary for JSON serialization."""
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SportSettings':
        """Create SportSettings instance from dictionary."""
        return cls()

    def to_json(self) -> str:
        """Convert SportSettings instance to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'SportSettings':
        """Create SportSettings instance from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class WorkoutDoc:
    description: Optional[str] = None
    description_locale: Optional[Dict[str, str]] = None
    duration: Optional[int] = None
    distance: Optional[float] = None
    ftp: Optional[int] = None
    lthr: Optional[int] = None
    threshold_pace: Optional[float] = None  # meters/sec
    pace_units: Optional[PaceUnits] = None
    sportSettings: Optional[SportSettings] = None
    category: Optional[str] = None
    target: Optional[WorkoutTarget] = None
    steps: Optional[List[Step]] = None
    zoneTimes: Optional[List[Union[int, Any]]] = None  # sometimes array of ints otherwise array of objects
    options: Optional[Dict[str, str]] = None
    locales: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert WorkoutDoc instance to dictionary for JSON serialization."""
        data = {}
        if self.description is not None:
            data['description'] = self.description
        if self.description_locale is not None:
            data['description_locale'] = self.description_locale
        if self.duration is not None:
            data['duration'] = self.duration
        if self.distance is not None:
            data['distance'] = self.distance
        if self.ftp is not None:
            data['ftp'] = self.ftp
        if self.lthr is not None:
            data['lthr'] = self.lthr
        if self.threshold_pace is not None:
            data['threshold_pace'] = self.threshold_pace
        if self.pace_units is not None:
            data['pace_units'] = self.pace_units.value
        if self.sportSettings is not None:
            data['sportSettings'] = self.sportSettings.to_dict()
        if self.category is not None:
            data['category'] = self.category
        if self.target is not None:
            data['target'] = self.target.value
        if self.steps is not None:
            data['steps'] = [step.to_dict() for step in self.steps]
        if self.zoneTimes is not None:
            data['zoneTimes'] = self.zoneTimes
        if self.options is not None:
            data['options'] = self.options
        if self.locales is not None:
            data['locales'] = self.locales
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkoutDoc':
        """Create WorkoutDoc instance from dictionary."""
        kwargs = {}
        if 'description' in data:
            kwargs['description'] = data['description']
        if 'description_locale' in data:
            kwargs['description_locale'] = data['description_locale']
        if 'duration' in data:
            kwargs['duration'] = data['duration']
        if 'distance' in data:
            kwargs['distance'] = data['distance']
        if 'ftp' in data:
            kwargs['ftp'] = data['ftp']
        if 'lthr' in data:
            kwargs['lthr'] = data['lthr']
        if 'threshold_pace' in data:
            kwargs['threshold_pace'] = data['threshold_pace']
        if 'pace_units' in data:
            kwargs['pace_units'] = PaceUnits(data['pace_units'])
        if 'sportSettings' in data:
            kwargs['sportSettings'] = SportSettings.from_dict(data['sportSettings'])
        if 'category' in data:
            kwargs['category'] = data['category']
        if 'target' in data:
            kwargs['target'] = WorkoutTarget(data['target'])
        if 'steps' in data:
            kwargs['steps'] = [Step.from_dict(step) for step in data['steps']]
        if 'zoneTimes' in data:
            kwargs['zoneTimes'] = data['zoneTimes']
        if 'options' in data:
            kwargs['options'] = data['options']
        if 'locales' in data:
            kwargs['locales'] = data['locales']
        return cls(**kwargs)

    def to_json(self) -> str:
        """Convert WorkoutDoc instance to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'WorkoutDoc':
        """Create WorkoutDoc instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def __str__(self) -> str:
        val = ""
        if self.description is not None:
            val += f"{self.description}\n"
        if self.steps is not None:
            for step in self.steps:
                val += step.__str__() + "\n"
        return val