"""Security analyzer stub module."""


def analyze_security(skill_content: str) -> dict:
    return {"risk_level": "low", "findings": [], "checked_chars": len(skill_content)}
