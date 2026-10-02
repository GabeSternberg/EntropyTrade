"""PydanticAI research pipeline. ``pydantic_ai`` is imported only in this package.

Provider requests are blocked on import. The demo uses TestModel.
"""

from entropytrade.agents.guard import block_provider_requests

block_provider_requests()
