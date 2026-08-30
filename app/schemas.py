from typing import Literal

from pydantic import BaseModel, Field

Topic = Literal["general", "news"]


class WebSearchInput(BaseModel):
    """Input contract for the ``web_search`` MCP tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=400,
        description="Natural-language search query.",
    )
    max_results: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Desired number of results. Clamped server-side to the configured "
            "limit. Defaults to the server default when omitted."
        ),
    )
    topic: Topic = Field(
        default="general",
        description="Search topic. 'news' biases toward recent articles.",
    )


class WebSearchResultItem(BaseModel):
    title: str
    url: str
    content: str = Field(description="Relevant extracted snippet for the result.")
    score: float = Field(description="Provider relevance score (higher is better).")
    published_date: str | None = Field(
        default=None,
        description="Publication date when the provider supplies one (mainly news).",
    )


class WebSearchResponse(BaseModel):
    """Output contract for the ``web_search`` MCP tool."""

    query: str = Field(description="The query that was executed.")
    provider: str = Field(description="Identifier of the search provider used.")
    result_count: int
    results: list[WebSearchResultItem]
