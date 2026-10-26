"""Internal domain router: service metadata and health probes.

Mounted at the application root (not under the versioned API prefix) so probes
and metadata are stable across API versions.
"""

from __future__ import annotations

from fastapi import APIRouter

from internal import handlers
from internal.models import Liveness, Readiness, ServiceInfo

router = APIRouter(tags=["internal"])

router.add_api_route(
    "/",
    handlers.service_info,
    methods=["GET"],
    response_model=ServiceInfo,
    summary="Service root",
)
router.add_api_route(
    "/health/live",
    handlers.liveness,
    methods=["GET"],
    response_model=Liveness,
    summary="Liveness probe",
)
router.add_api_route(
    "/health/ready",
    handlers.readiness,
    methods=["GET"],
    response_model=Readiness,
    summary="Readiness probe",
)
