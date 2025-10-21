# app/endpoints/max_backtest.py
from typing import Optional, Tuple, Dict, Any
from fastapi import HTTPException, UploadFile

from app.services.orca_max_backtesting.helper import read_bytes_cleaned
from app.services.orca_max_backtesting.orca_enums import TeamWay
from app.services.orca_max_backtesting.run import run_single


async def run_max_backtest_logic(
    *,
    account_name: str,
    mode: str,
    contract: str,
    max_mode_value: str,
    point_key: str,
    exit_strategy_key: str,
    notes: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    file: Optional[UploadFile] = None,
) -> Dict[str, Any]:
    """
    Core logic for the /run-bot/max-backtest endpoint.

    Rules:
    - If a file is provided, use it and ignore date range.
    - Else, require date_from and date_to.
    - 'mode' is always backtesting (per router comment), but still passed through.
    """
    # Validate the enum / mode early (keeps failure noise out of the route)
    try:
        max_mode = TeamWay(max_mode_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid maxMode: {e}")

    # 1) File path: parse and run
    if file:
        contents = await file.read()
        if contents is None or len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Parse uploaded dataset
        data, all_data = read_bytes_cleaned(contents, rows=-1)

        # Run your engine
        result, order_points_completed_dict = run_single(
            contract,
            data,
            data_name=f"{file.filename}-v2",
            way=max_mode,
            exit_strategy_key=exit_strategy_key,
            points_key=point_key,
        )

        return {
            "result": result,
            "trades": order_points_completed_dict,
            "meta": {
                "source": "file",
                "filename": file.filename,
                "accountName": account_name,
                "mode": mode,
                "notes": notes,
            },
        }

    # 2) Date-range path: both dates must be present
    if not date_from or not date_to:
        raise HTTPException(
            status_code=400,
            detail="Either upload a file OR provide both dateFrom and dateTo.",
        )

    # Load time-bounded data (implement this inside core.data_io)
    try:
        data, data_name = _load_data_for_range(contract, date_from, date_to)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e}")

    # Run your engine
    result, order_points_completed_dict = run_single(
        contract,
        data,
        data_name=data_name,
        way=max_mode,
        exit_strategy_key=exit_strategy_key,
        points_key=point_key,
    )

    return {
        "result": result,
        "trades": order_points_completed_dict,
        "meta": {
            "source": "date_range",
            "dateFrom": date_from,
            "dateTo": date_to,
            "accountName": account_name,
            "mode": mode,
            "notes": notes,
        },
    }


def _load_data_for_range(
    contract: str, date_from: str, date_to: str
) -> Tuple[Any, str]:
    """
    Fetches/constructs the dataset for a date range.
    Returns (data, data_name).
    """
    # You can do validation/conversion here if your fetch expects datetimes.
    data = fetch_data_between_dates(contract=contract, start=date_from, end=date_to)
    if data is None:
        raise ValueError("No data returned for the provided date range.")

    data_name = f"{contract}-{date_from}_to_{date_to}"
    return data, data_name
