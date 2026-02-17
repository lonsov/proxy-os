"""job_search_agent.py - Job Search Agent execution."""

import json
import os

from dotenv import load_dotenv

from clients.browser_use_client import BrowserUseClient

load_dotenv()


class JobSearchAgent:
    """Manages job search operations using Browser Use."""

    def __init__(self):
        """Initialize job search agent with Google API key from .env."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env")
        self.client = BrowserUseClient(api_key=self.api_key)

    def execute_search(self, params: dict) -> str:
        """Execute job search with structured output schema."""
        role = (params.get("role") or "").strip()
        company = (params.get("company") or "").strip()
        location = (params.get("location") or "").strip()
        experience_level = (params.get("experience_level") or "").strip()
        job_type = (params.get("job_type") or "").strip()
        work_mode = (params.get("work_mode") or "").strip()
        skills_keywords = params.get("skills_keywords")
        exclude_keywords = params.get("exclude_keywords")
        posted_within_days = params.get("posted_within_days")

        if isinstance(skills_keywords, list):
            skills_keywords = ", ".join(str(k).strip() for k in skills_keywords if str(k).strip())
        else:
            skills_keywords = (skills_keywords or "").strip()
        if isinstance(exclude_keywords, list):
            exclude_keywords = ", ".join(str(k).strip() for k in exclude_keywords if str(k).strip())
        else:
            exclude_keywords = (exclude_keywords or "").strip()
        try:
            posted_within_days = int(posted_within_days) if str(posted_within_days).strip() else None
        except (TypeError, ValueError):
            posted_within_days = None

        if not role:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Missing required role for job search.",
                    "message": "Please provide a specific role/title.",
                },
                indent=2,
            )

        try:
            # Build the search query
            query = (
                f"Search for {role} job listings on official company career pages and job board platforms "
                "(NOT LinkedIn posts or feed)."
            )
            if location:
                query += f" Prefer positions in {location}."
            if posted_within_days is not None:
                query += f" Focus on jobs posted within the last {posted_within_days} days."
            if company:
                query += f" Prioritize {company} positions."
            if experience_level:
                query += f" Prefer {experience_level} level roles."
            if job_type:
                query += f" Job type preference: {job_type}."
            if work_mode:
                query += f" Work mode preference: {work_mode}."
            if skills_keywords:
                query += f" Must include these keywords when possible: {skills_keywords}."
            if exclude_keywords:
                query += f" Exclude roles containing these keywords: {exclude_keywords}."

            query += """

CRITICAL RULES:
- applicationUrl MUST be a direct link to an actual job posting page where someone clicks "Apply"
- ONLY return URLs from: company career sites, boards.greenhouse.io, jobs.lever.co, myworkdayjobs.com, icims.com, or linkedin.com/jobs/view/XXXXXXXXX
- NEVER return: linkedin.com/posts/, linkedin.com/feed/, lnkd.in/ shortened links, or mailto: links
- Each result must be a real, individual job posting (not a search results page)
- Verify each result is relevant to the requested role/title and responsibilities"""

            # Define structured output schema
            schema = {
                "type": "object",
                "properties": {
                    "jobs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "jobTitle": {
                                    "type": "string",
                                    "description": "Exact job title as posted",
                                },
                                "companyName": {
                                    "type": "string",
                                    "description": "Hiring company name",
                                },
                                "location": {
                                    "type": "string",
                                    "description": "City, State or Remote",
                                },
                                "postingDate": {
                                    "type": "string",
                                    "description": "Date posted in YYYY-MM-DD format",
                                },
                                "applicationUrl": {
                                    "type": "string",
                                    "description": "Direct apply URL. MUST be from: company careers page, greenhouse.io, lever.co, workday, icims, or linkedin.com/jobs/view/NUMBERS. NEVER linkedin.com/posts/ or lnkd.in/ links.",
                                },
                                "jobDescriptionSummary": {
                                    "type": "string",
                                    "description": "Key requirements and responsibilities in 2-3 sentences",
                                },
                                "salaryRange": {
                                    "type": "string",
                                    "description": "Salary range if available, otherwise empty string",
                                },
                                "experienceLevel": {
                                    "type": "string",
                                    "description": "Entry, Mid, Senior, Lead, or Staff",
                                },
                                "source": {
                                    "type": "string",
                                    "description": "Where listing was found: company_careers, greenhouse, lever, workday, indeed, linkedin_jobs",
                                },
                            },
                            "required": [
                                "jobTitle",
                                "companyName",
                                "location",
                                "applicationUrl",
                                "jobDescriptionSummary",
                                "source",
                            ],
                        },
                    },
                    "totalJobsFound": {"type": "integer"},
                    "searchDate": {"type": "string"},
                },
                "required": ["jobs", "totalJobsFound", "searchDate"],
            }

            # Call Browser Use with structured output
            response = self.client.search(
                query=query,
                depth="standard",
                output_type="structured",
                structured_output_schema=json.dumps(schema),
                include_sources=False,
                include_images=False,
            )

            return json.dumps(
                {
                    "status": "success",
                    "query": f"{role} in {location}" + (f" at {company}" if company else ""),
                    "response": response,
                    "next_steps": "I can research the company, tailor your resume, or draft a cover letter for any of these roles.",
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "error": str(e),
                    "message": "Failed to fetch job results. Please check your API key and try again.",
                },
                indent=2,
            )


# Backward-compat alias for any old imports.
JobSearcher = JobSearchAgent


__all__ = ["JobSearchAgent", "JobSearcher"]
