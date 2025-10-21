"""
Optimized version using PostgreSQL JSONB operators
This is more efficient for large datasets
"""

def find_duplicate_configs_optimized(strategy_config: dict, status_filter: str = None) -> list:
    """
    Find all run configurations with matching strategy_config using JSONB containment.
    More efficient for large datasets.
    
    Args:
        strategy_config: The identifying fields to match against
        status_filter: Optional status filter (e.g., "running" to find only active duplicates)
    
    Returns:
        List of matching run config records
    """
    import json
    from app.services.orca_supabase.orca_supabase import SUPABASE
    
    # Use the @> (contains) operator for JSONB
    # This checks if strategy_config contains the given fields
    json_str = json.dumps(strategy_config)
    
    query = (
        SUPABASE.table("run_configs")
        .select("*")
        .filter("strategy_config", "cs", json_str)  # 'cs' = contains (superset)
        .order("created_at", desc=True)
    )
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    response = query.execute()
    all_records = response.data or []
    
    # Still filter manually for exact match (not just containment)
    matching_records = []
    for record in all_records:
        if record.get("strategy_config") == strategy_config:
            matching_records.append(record)
    
    return matching_records


# Example usage comparison:

"""
Current approach (simple, always works):
- Fetches all records
- Filters in Python
- Good for small-medium datasets

Optimized approach (for large datasets):
- Uses JSONB containment to reduce fetched records
- Then filters for exact match in Python
- Better for 1000+ records
"""
