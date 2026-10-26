"""Response models for the internal domain."""

from __future__ import annotations

from pydantic import BaseModel


class ServiceInfo(BaseModel):
    service: str
    version: str
    docs: str


class Liveness(BaseModel):
    status: str


class Readiness(BaseModel):
    status: str
    environment: str
    checks: dict[str, str]
