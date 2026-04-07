"""Base class for all booking/scheduling platform integrations."""

from abc import abstractmethod
from datetime import datetime, date
from typing import Optional, List

from app.integrations.base import BaseIntegration
from app.integrations.booking.models import (
    StandardAppointment, StandardClient, StandardService,
    StandardProvider, TimeSlot,
)


class BaseBookingIntegration(BaseIntegration):
    """Every booking integration must implement these methods."""

    # --- Reading appointments ---

    @abstractmethod
    async def get_upcoming_appointments(
        self, business_id: str, days_ahead: int = 7
    ) -> List[StandardAppointment]:
        ...

    @abstractmethod
    async def get_appointment_detail(
        self, business_id: str, appointment_id: str
    ) -> StandardAppointment:
        ...

    @abstractmethod
    async def get_todays_appointments(self, business_id: str) -> List[StandardAppointment]:
        ...

    @abstractmethod
    async def get_new_appointments_since(
        self, business_id: str, since: datetime
    ) -> List[StandardAppointment]:
        ...

    @abstractmethod
    async def get_cancelled_appointments_since(
        self, business_id: str, since: datetime
    ) -> List[StandardAppointment]:
        ...

    # --- Clients ---

    @abstractmethod
    async def get_client(self, business_id: str, client_id: str) -> StandardClient:
        ...

    @abstractmethod
    async def search_clients(self, business_id: str, query: str) -> List[StandardClient]:
        ...

    @abstractmethod
    async def get_client_appointment_history(
        self, business_id: str, client_id: str
    ) -> List[StandardAppointment]:
        ...

    # --- Services ---

    @abstractmethod
    async def get_services(self, business_id: str) -> List[StandardService]:
        ...

    # --- Providers ---

    @abstractmethod
    async def get_providers(self, business_id: str) -> List[StandardProvider]:
        ...

    # --- Writing ---

    @abstractmethod
    async def create_appointment(
        self, business_id: str, client_id: str, service_id: str,
        provider_id: str, start_time: datetime, notes: Optional[str] = None,
    ) -> StandardAppointment:
        ...

    @abstractmethod
    async def cancel_appointment(
        self, business_id: str, appointment_id: str, reason: Optional[str] = None,
    ) -> bool:
        ...

    # --- Availability ---

    @abstractmethod
    async def get_available_slots(
        self, business_id: str, service_id: str,
        provider_id: Optional[str] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
    ) -> List[TimeSlot]:
        ...
