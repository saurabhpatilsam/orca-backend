import datetime
import json
from typing import Optional, List, Union, Dict
from fastapi import APIRouter, HTTPException, Body, Query, BackgroundTasks
from fastapi import UploadFile, File, Form
from starlette.responses import JSONResponse
from app.api.v1.endpoints.max_backtest import run_max_backtest_logic
from app.api.v1.endpoints.max_live import run_orca_system
from app.services.orca_max.helpers.enums import ENVIRONMENT, TeamWay, PointType, Contract, PointPosition
from app.services.orca_max.schemas import AccountConfig
from app.services.orca_max_backtesting.helper import read_bytes_cleaned
from app.services.orca_supabase.orca_supabase import (
    get_all_run_configs,
    get_active_run_configs,
    update_run_config_status,
    find_duplicate_configs,
    has_active_duplicate
)
from app.services.orca_supabase.config_utils import normalize_strategy_config

max_router = APIRouter(prefix="/run-bot")


def run_orca_system_background(run_config: Dict, run_id: int):
    """
    Background task wrapper for running the Orca system.
    Updates status in database as it progresses.
    """
    from app.utils.logging_setup import logger
    from app.services.orca_supabase.orca_supabase import update_run_config_status
    
    try:
        logger.info(f"🚀 Starting background execution for run_id: {run_id}")
        
        # Update status to running
        update_run_config_status(run_id, "running")
        
        # Run the actual system
        result = run_orca_system(run_config)
        
        # Mark as completed
        update_run_config_status(run_id, "completed")
        logger.info(f"✅ Run {run_id} completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in background task for run_id {run_id}: {str(e)}")
        update_run_config_status(run_id, "failed")
        logger.error(f"Run {run_id} failed with error: {str(e)}")


@max_router.post("/max-backtest")
async def run_bot_backtesting(
    accountName: str = Form(...),
    mode: str = Form(...),
    contract: str = Form(...),
    maxMode: str = Form(...),
    point_key: str = Form(...),
    exit_strategy_key: str = Form(...),
    notes: Optional[str] = Form(None),
    dateFrom: Optional[str] = Form(None),
    dateTo: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    try:
        payload = await run_max_backtest_logic(
            account_name=accountName,
            mode=mode,
            contract=contract,
            max_mode_value=maxMode,
            point_key=point_key,
            exit_strategy_key=exit_strategy_key,
            notes=notes,
            date_from=dateFrom,
            date_to=dateTo,
            file=file,
        )
        return JSONResponse(content=payload, status_code=200)

    except HTTPException:
        # Re-raise FastAPI-native errors as-is
        raise
    except Exception as e:
        # Fall-through for anything unexpected
        raise HTTPException(status_code=500, detail=str(e))

@max_router.post("/max")
async def run_bot_max(
    background_tasks: BackgroundTasks,
    accountName: str = Form("APEX_136189"),
    contract: Union[Contract] = Form(),
    maxMode: Optional[str] = Form(...),
    trading_mode: Union[TeamWay] = Form(),
    trading_side: Union[PointType] = Form(),
    point_strategy_key: str = Form("15_7_5_2"),
    point_position: Union[PointPosition] = Form(),
    exit_strategy_key: str = Form("15_15"),
    dateFrom: Optional[datetime.datetime] = Form(),
    dateTo: Optional[datetime.datetime] = Form(),
    # file: Optional[UploadFile] = File(None),
    # parse these from form too for consistency
    quantity: int = Form(1),
    environment: Optional[ENVIRONMENT] = Form(),
    # accept JSON string; client sends accounts_ids='[{"id": "...", ...}]'
    # [{"tv_id"="D18156705", "ta_id"="PAAPEX1361890000008"}]
    accounts_ids: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    user: Optional[str] = Form("system", description="User who is running the bot"),
):

    try:
        file = None
        # 1) File path: parse and run
        if file:
            contents = await file.read()
            if contents is None or len(contents) == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            # Parse uploaded dataset
            data, all_data = read_bytes_cleaned(contents, rows=-1)

        parsed_accounts: Optional[List[AccountConfig]] = None
        if accounts_ids and accounts_ids != [""]:
            parsed = json.loads(accounts_ids)
            # Pydantic-validate each entry
            parsed_accounts = [AccountConfig(**item) for item in parsed]

        run_config = {
            "main_account": accountName,
            "instrument_name": contract.value,
            "way": TeamWay(trading_mode),
            "point_type": PointType(trading_side),
            "point_strategy_key": point_strategy_key,
            "point_position": point_position,
            "exit_strategy_key": exit_strategy_key,
            "quantity": quantity,
            "environment": (
                environment.value
                if isinstance(environment, ENVIRONMENT)
                else environment
            ),
            "price_file": file,  # whatever your system expects here
            "start_time": dateFrom,
            "end_time": dateTo,
            "accounts_ids": parsed_accounts,
            "notes": notes,
            "user": user,  # Add user to config for tracking
        }

        # Store config in database with "queued" status
        from app.services.orca_supabase.orca_supabase import insert_run_config
        from app.services.orca_supabase.config_utils import extract_strategy_config
        from app.utils.logging_setup import logger
        
        # Extract strategy config for duplicate detection
        strategy_config = extract_strategy_config(run_config)
        
        # Check for active duplicates
        has_duplicate, duplicate_records = has_active_duplicate(strategy_config)
        
        # Create serializable copy of config
        config_to_store = {
            k: v if not hasattr(v, '__dict__') else str(v)
            for k, v in run_config.items()
        }
        
        # Handle datetime serialization
        if config_to_store.get("start_time"):
            config_to_store["start_time"] = str(config_to_store["start_time"])
        if config_to_store.get("end_time"):
            config_to_store["end_time"] = str(config_to_store["end_time"])
        
        # Insert with "queued" status
        record = insert_run_config(
            config_to_store,
            strategy_config=strategy_config,
            created_by=user,
            status="queued"
        )
        
        run_id = record.get("id") if record else None
        
        if not run_id:
            raise HTTPException(status_code=500, detail="Failed to create run configuration")
        
        logger.info(f"📋 Run config queued with ID: {run_id}")
        
        if has_duplicate:
            duplicate_ids = [rec.get("id") for rec in duplicate_records]
            logger.warning(f"⚠️  Duplicate configuration detected. Active runs: {duplicate_ids}")
        
        # Add background task to process the run
        background_tasks.add_task(run_orca_system_background, run_config, run_id)
        
        # Return immediately with run_id
        return JSONResponse(content={
            "status": "queued",
            "message": "Trading bot queued for execution",
            "run_id": run_id,
            "is_duplicate": has_duplicate,
            "duplicate_run_ids": [rec.get("id") for rec in duplicate_records] if has_duplicate else [],
            "note": "Use GET /api/v1/run-bot/configs/{run_id} to check status"
        }, status_code=202)  # 202 Accepted
    except HTTPException:
        raise
    except Exception as e:
        raise e
        raise HTTPException(status_code=500, detail="Internal server error")


@max_router.get("/configs/{run_id}")
async def get_run_config_by_id(run_id: int):
    """
    Get a specific run configuration by ID.
    Use this to check the status of a queued/running job.
    
    Args:
        run_id: The ID of the run configuration
    
    Returns:
        Run configuration record with current status
    """
    try:
        all_configs = get_all_run_configs()
        config = next((c for c in all_configs if c.get("id") == run_id), None)
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Run config with ID {run_id} not found")
        
        return JSONResponse(content={"config": config}, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching config: {str(e)}")


@max_router.get("/configs")
async def get_run_configs(
    status: Optional[str] = Query(None, description="Filter by status (e.g., 'queued', 'running', 'completed', 'failed')")
):
    """
    Get all run configurations, optionally filtered by status.
    
    Args:
        status: Optional status filter ('queued', 'running', 'completed', 'failed', etc.)
    
    Returns:
        List of run configuration records
    """
    try:
        configs = get_all_run_configs(status_filter=status)
        return JSONResponse(content={"configs": configs, "count": len(configs)}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching configs: {str(e)}")


@max_router.get("/configs/active")
async def get_active_configs():
    """
    Get all active (running) run configurations.
    
    Returns:
        List of active run configuration records
    """
    try:
        configs = get_active_run_configs()
        return JSONResponse(content={"configs": configs, "count": len(configs)}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching active configs: {str(e)}")


@max_router.patch("/configs/{run_id}/status")
async def update_config_status(
    run_id: int,
    status: str = Body(..., embed=True, description="New status (e.g., 'stopped', 'completed', 'failed')")
):
    """
    Update the status of a run configuration.
    
    Args:
        run_id: The ID of the run configuration
        status: New status to set
    
    Returns:
        Updated run configuration record
    """
    try:
        updated_record = update_run_config_status(run_id, status)
        if not updated_record:
            raise HTTPException(status_code=404, detail=f"Run config with ID {run_id} not found")
        
        return JSONResponse(content={"config": updated_record}, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config status: {str(e)}")


@max_router.post("/configs/check-duplicate")
async def check_duplicate_config(strategy_config: Dict = Body(...)):
    """
    Check if a strategy configuration has duplicates.
    
    Provide the identifying fields:
    - instrument_name
    - way
    - point_type
    - point_strategy_key
    - point_position
    - exit_strategy_key
    
    Args:
        strategy_config: Dictionary with the identifying fields
    
    Returns:
        Information about duplicate configurations
    """
    try:
        # Normalize the strategy config for comparison
        normalized_config = normalize_strategy_config(strategy_config)
        
        # Check for active duplicates
        has_duplicate, duplicate_records = has_active_duplicate(normalized_config)
        
        # Also get all duplicates (including completed/failed)
        all_duplicates = find_duplicate_configs(normalized_config)
        
        return JSONResponse(content={
            "has_active_duplicate": has_duplicate,
            "active_duplicates": duplicate_records,
            "active_count": len(duplicate_records),
            "all_duplicates": all_duplicates,
            "total_count": len(all_duplicates),
            "strategy_config": normalized_config
        }, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking for duplicates: {str(e)}")


@max_router.get("/configs/{run_id}/duplicates")
async def get_config_duplicates(run_id: int):
    """
    Find all configurations that are duplicates of a specific run.
    
    Args:
        run_id: The ID of the run configuration to check
    
    Returns:
        List of duplicate configurations
    """
    try:
        # First, get the target config
        all_configs = get_all_run_configs()
        target_config = next((c for c in all_configs if c.get("id") == run_id), None)
        
        if not target_config:
            raise HTTPException(status_code=404, detail=f"Run config with ID {run_id} not found")
        
        strategy_config = target_config.get("strategy_config", {})
        
        # Find all duplicates (excluding the target itself)
        duplicates = find_duplicate_configs(strategy_config)
        duplicates = [d for d in duplicates if d.get("id") != run_id]
        
        return JSONResponse(content={
            "run_id": run_id,
            "strategy_config": strategy_config,
            "duplicates": duplicates,
            "count": len(duplicates)
        }, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding duplicates: {str(e)}")
