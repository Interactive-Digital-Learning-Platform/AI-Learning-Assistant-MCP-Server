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


PdfStatus = Literal["completed", "failed"]


class GeneratePdfInput(BaseModel):
    """Input contract for the ``generate_pdf`` MCP tool."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Document title. Also the default filename base.",
    )
    markdown_body: str = Field(
        ...,
        min_length=1,
        max_length=200_000,
        description=(
            "Finished document content as CommonMark markdown. The caller "
            "supplies the authored text; this tool does not generate it."
        ),
    )
    filename: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Optional download filename. Sanitised server-side; a '.pdf' "
            "suffix is enforced. Defaults to a slug of the title."
        ),
    )


class GeneratePdfResponse(BaseModel):
    """Output contract for the ``generate_pdf`` MCP tool."""

    status: PdfStatus
    document_id: str = Field(description="Opaque identifier; also the storage key prefix.")
    filename: str = Field(description="Download filename delivered to the end user.")
    mime_type: str = "application/pdf"
    page_count: int | None = Field(
        default=None,
        description="Rendered page count. Null when status is 'failed'.",
    )
    download_url: str | None = Field(
        default=None,
        description="Presigned GET URL. Null when status is 'failed'.",
    )
    expires_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC instant at which download_url stops working.",
    )
    error: str | None = Field(
        default=None,
        description="Short human-readable reason when status is 'failed'.",
    )
