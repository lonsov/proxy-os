# job_searcher.py — Job Search Tool Execution
# Handles job search functionality for the agent

import json
import os
from dotenv import load_dotenv
from browser_use_client import BrowserUseClient

load_dotenv()


class JobSearcher:
    """Manages job search operations using Browser Use."""
    
    def __init__(self):
        """Initialize job searcher with Google API key from .env."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env")
        self.client = BrowserUseClient(api_key=self.api_key)
    
    def execute_search(self, params: dict) -> str:
        """Execute job search with structured output schema."""
        role = (params.get("role") or "").strip()
        company = (params.get("company") or "").strip()
        location = params.get("location", "United States")

        if not role:
            return json.dumps({
                "status": "error",
                "error": "Missing required role for job search.",
                "message": "Please provide a specific role/title.",
            }, indent=2)
        
        try:
            # Build the search query
            query = f"Search for {role} job listings on official company career pages and job board platforms (NOT LinkedIn posts or feed). Find positions at major tech companies in the {location} posted within the last 7 days."
            if company:
                query += f" Prioritize {company} positions."
            
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
                                    "description": "Exact job title as posted"
                                },
                                "companyName": {
                                    "type": "string",
                                    "description": "Hiring company name"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "City, State or Remote"
                                },
                                "postingDate": {
                                    "type": "string",
                                    "description": "Date posted in YYYY-MM-DD format"
                                },
                                "applicationUrl": {
                                    "type": "string",
                                    "description": "Direct apply URL. MUST be from: company careers page, greenhouse.io, lever.co, workday, icims, or linkedin.com/jobs/view/NUMBERS. NEVER linkedin.com/posts/ or lnkd.in/ links."
                                },
                                "jobDescriptionSummary": {
                                    "type": "string",
                                    "description": "Key requirements and responsibilities in 2-3 sentences"
                                },
                                "salaryRange": {
                                    "type": "string",
                                    "description": "Salary range if available, otherwise empty string"
                                },
                                "experienceLevel": {
                                    "type": "string",
                                    "description": "Entry, Mid, Senior, Lead, or Staff"
                                },
                                "source": {
                                    "type": "string",
                                    "description": "Where listing was found: company_careers, greenhouse, lever, workday, indeed, linkedin_jobs"
                                }
                            },
                            "required": ["jobTitle", "companyName", "location", "applicationUrl", "jobDescriptionSummary", "source"]
                        }
                    },
                    "totalJobsFound": {
                        "type": "integer"
                    },
                    "searchDate": {
                        "type": "string"
                    }
                },
                "required": ["jobs", "totalJobsFound", "searchDate"]
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
            
            # Don't print raw response - let agent format it for display
            
            # Return structured response
            return json.dumps({
                "status": "success",
                "query": f"{role} in {location}" + (f" at {company}" if company else ""),
                "response": response,
                "next_steps": "I can research the company, tailor your resume, or draft a cover letter for any of these roles.",
            }, indent=2)
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
                "message": "Failed to fetch job results. Please check your API key and try again.",
            }, indent=2)
