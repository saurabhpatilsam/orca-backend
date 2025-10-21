import argparse
import pickle

from app.services.orca_max_backtesting.helper import read_file
from app.services.orca_max_backtesting.orca_enums import TeamWay
from app.services.orca_max_backtesting.run import run_single


# from orcaven.algorithm.abc_validator.helper import read_file, TeamWay
# from orcaven.algorithm.abc_validator.run import run_single


# Import necessary functions and classes here
# from your_module import read_file, run_single, TeamWay


def main(file_name, daily_data, way):
    data = read_file(file_name + ".txt", rows=-1)
    # plot_data2(data)
    # pickle.dump(data, open(f"files/data_50K{file_name}.pickle", "wb"))
    # data = pickle.load(open(f"files/data_50K{file_name}.pickle", "rb"))
    # file_name = 'data_NQ_07777'
    # data = pickle.load(open("files/data_NQ_07.pickle", "rb"))
    # run_single(data, data_name="NQ 09-24_07")
    # run(data, data_name=file_name+"-v2")
    run_single(data, data_name=file_name + "-v2", way=way)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run data processing and analysis.")
    parser.add_argument(
        "-f",
        "--file_name",
        type=str,
        default="NQ15-16 09-24.Last_timed2",
        help="The name of the file to process.",
    )
    parser.add_argument(
        "-d",
        "--daily_data",
        type=bool,
        default=True,
        help="Flag to indicate daily data processing.",
    )
    parser.add_argument(
        "-w",
        "--way",
        type=str,
        choices=["BT", "RE"],
        default="BreakThrough",
        help="Processing method to use.",
    )

    args = parser.parse_args()

    way = getattr(TeamWay, args.way)

    main(args.file_name, args.daily_data, way)
