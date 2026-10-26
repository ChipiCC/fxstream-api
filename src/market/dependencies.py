"""FastAPI dependencies for the process-local market runtime."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from market.runtime import MarketRuntime


def get_market(request: Request) -> MarketRuntime:
    runtime: MarketRuntime = request.app.state.market
    return runtime


MarketDep = Annotated[MarketRuntime, Depends(get_market)]
