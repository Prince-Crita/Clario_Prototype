"""Finance domain registration (plan §15.1).

Phase 6 added the datasets (the mirror) and the fixture source; Phase 7 the dashboard router;
Phase 9 the Finance Assistant.
"""

from __future__ import annotations

from clario.domains.finance.api import router
from clario.domains.finance.assistant.spec import ASSISTANT
from clario.domains.finance.datasets import DATASETS
from clario.domains.finance.testing.fixture_source import fixture_source
from clario.platform.integrations.contract import DomainModule

module = DomainModule(
    key="finance",
    name="Finance",
    description="Revenue, costs, cash, receivables and GST from your accounting system.",
    datasets=DATASETS,
    fixture_source=fixture_source,
    router=router,
    assistant=ASSISTANT,
)
