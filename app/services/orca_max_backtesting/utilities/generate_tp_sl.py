import json

from app.services.orca_max_backtesting.config import EXIT_STRATEGIES_COMPENSATION

# from orcaven.algorithm.abc_validator.config import EXIT_STRATEGIES_COMPENSATION

VERSION = 1


def generate_exit_strategies(companion_list):
    EXIT_STRATEGIES = {}
    for tp, sl in companion_list:
        key = f"{tp}_{sl}"
        EXIT_STRATEGIES[key] = {
            "TP": tp,
            "SL": sl,
            "result": {
                "long": {"LOOSING_TRADES": 0, "WINNING_TRADES": 0, "NotTriggered": 0},
                "short": {"LOOSING_TRADES": 0, "WINNING_TRADES": 0, "NotTriggered": 0},
            },
        }
    return EXIT_STRATEGIES


# Example usage:
EXIT_STRATEGIES = generate_exit_strategies(EXIT_STRATEGIES_COMPENSATION)

import pprint

pprint.pprint(EXIT_STRATEGIES)
# Converting to JSON string
json_string = json.dump(
    EXIT_STRATEGIES, open(f"output_json/exit_strategies_v{VERSION}.json", "w"), indent=4
)

# Print the resulting dictionary
