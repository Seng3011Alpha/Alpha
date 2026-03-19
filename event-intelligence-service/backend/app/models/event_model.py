#adage 3.0 data model aligned with the specification
#top-level: data_source, dataset_type, dataset_id, time_object, events
#event fields: time_object, event_type, attribute (flexible dict)
from pydantic import BaseModel
from typing import Optional, Any


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
