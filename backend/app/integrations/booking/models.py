"""Standard data models that normalize data from any booking platform."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List


@dataclass
class StandardClient:
    id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    created_at: Optional[datetime] = None
    total_appointments: Optional[int] = None
    last_appointment_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    source_platform: str = ""
    raw_data: dict = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return "{} {}".format(self.first_name, self.last_name).strip()


@dataclass
class StandardService:
    id: str
    name: str
    category: Optional[str] = None
    duration_minutes: int = 0
    price: Optional[float] = None
    description: Optional[str] = None
    source_platform: str = ""


@dataclass
class StandardProvider:
    id: str
    first_name: str
    last_name: str
    title: Optional[str] = None
    email: Optional[str] = None
    services: List[str] = field(default_factory=list)
    source_platform: str = ""

    @property
    def full_name(self) -> str:
        return "{} {}".format(self.first_name, self.last_name).strip()


@dataclass
class StandardAppointment:
    id: str
    client: Optional[StandardClient] = None
    service: Optional[StandardService] = None
    provider: Optional[StandardProvider] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: int = 0
    status: str = "confirmed"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_platform: str = ""
    raw_data: dict = field(default_factory=dict)


@dataclass
class TimeSlot:
    start_time: datetime
    end_time: datetime
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    available: bool = True
