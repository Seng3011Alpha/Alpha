from pydantic import BaseModel
from typing import Optional, Any

"""
ADAGE 3.0 Data Model - aligned with specification.
Top-level: data_source, dataset_type, dataset_id, time_object, events.
Event: time_object (timestamp, duration?, duration_unit?, timezone), event_type, attribute (flexible dict).
"""


class TimeObject(BaseModel):
    timestamp: str
    duration: Optional[int] = None
    duration_unit: Optional[str] = None
    timezone: str = "UTC"


class Event(BaseModel):
    time_object: TimeObject
    event_type: str
    attribute: dict[str, Any]


class EventDataset(BaseModel):
    data_source: str
    dataset_type: str
    dataset_id: str
    time_object: TimeObject
    events: list[Event] = []
