from pydantic import BaseModel, Field


class SeoReview(BaseModel):
    score: int = Field(
        ge=1, le=10, description="Overall SEO quality from 1 (poor) to 10 (excellent)"
    )
    summary: str = Field(
        description="One or two sentences on the main strengths and weaknesses"
    )
    suggested_title: str = Field(
        description="An improved page title, under 60 characters"
    )
    suggested_description: str = Field(
        description="An improved meta description, under 160 characters"
    )
    issues: list[str] = Field(
        description="Specific, actionable problems, most important first"
    )
