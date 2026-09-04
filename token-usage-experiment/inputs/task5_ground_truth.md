# Task 5 — Ground truth for structured extraction

Target JSON schema:
```json
{
  "name": "Alex Chen",
  "years_experience": 9,
  "skills": ["Go", "Python", "TypeScript", "Node.js", "Kafka", "Flink",
             "Postgres", "Redis", "Kubernetes", "Terraform", "AWS", "gRPC",
             "REST", "distributed tracing", "on-call"],
  "most_recent_role": {
    "title": "Staff Software Engineer",
    "company": "Northwind Health",
    "dates": "Mar 2023 to present"
  }
}
```

Scoring (5 items):
1. `name` exactly "Alex Chen"
2. `years_experience` = 9 (integer)
3. `skills` is an array containing at least 8 of the listed skills
4. `most_recent_role.title` = "Staff Software Engineer"
5. `most_recent_role.company` = "Northwind Health"

Additionally, output must be valid JSON and match schema shape (no extra required fields missing, no wrong types).

- All 5 correct + valid JSON: success
- 3-4 correct + valid JSON: partial
- Otherwise (invalid JSON or <3 fields): fail
