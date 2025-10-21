import os
from supabase import create_client, Client
from dotenv import load_dotenv

from app.utils.decorators.timing.time import time_it

# Load .env
load_dotenv()

# SUPABASE_URL = os.getenv("SUPABASE_URL", default='https://dcoukhtfcloqpfmijock.supabase.co')
# SUPABASE_KEY = os.getenv("SUPABASE_KEY", default='sb_secret__t3NV0SUY8ywb2y_44jRDA_JOcR--G_')
# SUPABASE_URL = os.getenv("SUPABASE_URL", default="https://dcoukhtfcloqpfmijock.supabase.co")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY", default="sb_secret__t3NV0SUY8ywb2y_44jRDA_JOcR--G_")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")




from zoneinfo import ZoneInfo
# Create Supabase client
SUPABASE: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
LONDON = ZoneInfo("Europe/London")


def stream_ticks(table: str, page_size: int = 1000):
    start = 0
    while True:
        end = start + page_size - 1
        resp = (
            SUPABASE.table(table)
              .select("*")
              .order("ts", desc=True)
              .range(start, end)
              .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for row in batch:
            yield row
        if len(batch) < page_size:
            break
        start += page_size

from datetime import datetime, timedelta

def stream_ticks_keyset1(
    table: str,
    data_from: datetime,
    data_to: datetime,
    page_size: int = 1000
):
    """
    Stream tick data from Supabase in descending order,
    restricted to minute-level range [data_from, data_to).

    Both datetimes are truncated to the start of their minute.
    Yields rows one by one.
    """
    # --- truncate to minute precision ---
    data_from = data_from.replace(second=0, microsecond=0)
    data_to = data_to.replace(second=0, microsecond=0)

    # make sure we include the entire last minute
    data_to_exclusive = data_to + timedelta(minutes=1)

    # Convert to ISO strings for Supabase filters
    from_iso = data_from.isoformat()
    to_iso = data_to_exclusive.isoformat()

    last_ts = None
    last_id = None

    while True:
        q = (
            SUPABASE.table(table)
            .select("*")
            .order("ts", desc=False)
            .gte("ts", from_iso)   # ts >= data_from
            .lt("ts", to_iso)      # ts < data_to + 1 min
            .limit(page_size)
        )

        if last_ts is not None:
            # Keyset pagination: fetch only rows before the last seen timestamp/id
            q = q.or_(f"ts.lt.{last_ts},and(ts.eq.{last_ts},id.lt.{last_id})")

        resp = q.execute()
        batch = resp.data or []
        if not batch:
            break

        for row in batch:
            yield row

        if len(batch) < page_size:
            break

        # advance cursor
        last_ts = batch[-1]["ts"]
        last_id = batch[-1]["id"]


def stream_ticks_keyset(
    table: str,
    data_from: datetime,
    data_to: datetime,
    page_size: int = 1000
):
    """
    Stream tick data from Supabase in ascending order using keyset pagination
    over the composite key (ts, id), restricted to [data_from, data_to] at
    minute precision.
    """
    # --- truncate to minute precision ---
    data_from = data_from.replace(second=0, microsecond=0)
    data_to = data_to.replace(second=0, microsecond=0)

    # include the entire last minute
    data_to_exclusive = data_to + timedelta(minutes=1)

    from_iso = data_from.isoformat()
    to_iso = data_to_exclusive.isoformat()

    last_ts = None
    last_id = None

    while True:
        q = (
            SUPABASE.table(table)
            .select("*")
            # order by BOTH keys to match the keyset predicate
            .order("ts", desc=False)
            .order("id", desc=False)
            .gte("ts", from_iso)
            .lt("ts", to_iso)
            .limit(page_size)
        )

        if last_ts is not None:
            # For ASC order, use "greater than" for the cursor
            # (ts, id) > (last_ts, last_id)
            q = q.or_(
                f"ts.gt.{last_ts},and(ts.eq.{last_ts},id.gt.{last_id})"
            )

        resp = q.execute()
        batch = resp.data or []
        if not batch:
            break

        for row in batch:
            yield row

        # advance cursor to the last row we returned
        last_ts = batch[-1]["ts"]
        last_id = batch[-1]["id"]

        # when the final page is shorter than page_size, we’re done
        if len(batch) < page_size:
            break


def insert_run_config(
    config: dict,
    strategy_config: dict,
    created_by: str = "system",
    status: str = "running"
) -> dict:
    """
    Insert a new run configuration into Supabase.
    
    Args:
        config: The complete run configuration dictionary
        strategy_config: The identifying fields for duplicate detection
        created_by: The user who created the config (default: "system")
        status: The status of the run (default: "running")
    
    Returns:
        The inserted record with id and created_at
    """
    from datetime import datetime, timezone
    
    record = {
        "config": config,
        "strategy_config": strategy_config,
        "created_by": created_by,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    response = SUPABASE.table("run_configs").insert(record).execute()
    return response.data[0] if response.data else None


def update_run_config_status(run_id: int, status: str) -> dict:
    """
    Update the status of a run configuration.
    
    Args:
        run_id: The ID of the run config record
        status: The new status (e.g., "completed", "failed", "stopped")
    
    Returns:
        The updated record
    """
    from datetime import datetime, timezone
    
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    response = (
        SUPABASE.table("run_configs")
        .update(update_data)
        .eq("id", run_id)
        .execute()
    )
    return response.data[0] if response.data else None


def get_all_run_configs(status_filter: str = None) -> list:
    """
    Get all run configurations, optionally filtered by status.
    
    Args:
        status_filter: Optional status to filter by (e.g., "running", "completed")
    
    Returns:
        List of run config records
    """
    query = SUPABASE.table("run_configs").select("*").order("created_at", desc=True)
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    response = query.execute()
    return response.data or []


def get_active_run_configs() -> list:
    """
    Get all active (running) run configurations.
    
    Returns:
        List of active run config records
    """
    return get_all_run_configs(status_filter="running")


def find_duplicate_configs(strategy_config: dict, status_filter: str = None) -> list:
    """
    Find all run configurations with matching strategy_config.
    
    Args:
        strategy_config: The identifying fields to match against
        status_filter: Optional status filter (e.g., "running" to find only active duplicates)
    
    Returns:
        List of matching run config records
    """
    # For JSONB columns, we need to use the containment operator (@>)
    # or filter manually since exact equality on JSONB can be tricky
    query = (
        SUPABASE.table("run_configs")
        .select("*")
        .order("created_at", desc=True)
    )
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    response = query.execute()
    all_records = response.data or []
    
    # Filter manually to find exact matches
    # This is more reliable than JSONB equality in PostgREST
    matching_records = []
    for record in all_records:
        if record.get("strategy_config") == strategy_config:
            matching_records.append(record)
    
    return matching_records


def has_active_duplicate(strategy_config: dict) -> tuple[bool, list]:
    """
    Check if there's an active (running) configuration with the same strategy.
    
    Args:
        strategy_config: The identifying fields to check
    
    Returns:
        Tuple of (has_duplicate: bool, duplicate_records: list)
    """
    duplicates = find_duplicate_configs(strategy_config, status_filter="running")
    return len(duplicates) > 0, duplicates


if __name__ == '__main__':
    # Example: stream data between July 24 and July 25, 2025
    start_time = datetime(2025, 7, 25, 15, 0,  tzinfo=LONDON)  # from 18:05
    end_time = datetime(2025, 7, 25, 18, 10, tzinfo=LONDON) # until 18:10
    for tick in stream_ticks_keyset("ticks_nq", start_time, end_time):
        # do something useful here
        print(tick)

    # dd= get_all_data()
    # d=3