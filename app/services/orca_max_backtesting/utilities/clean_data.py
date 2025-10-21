from enum import Enum

from app.services.orca_max_backtesting.helper import read_file_plain
from app.utils.decorators.timing.time import time_it


# from orcaven.algorithm.abc_validator.helper import read_file_plain
# from orcaven.decorators.timing.time import time_it


class PriceLevel(Enum):
    ASK = 1
    BID = 2
    LAST = 3


class DataCleaner:
    def __init__(self, data, file_name, price_level=PriceLevel.LAST):
        self.data = data
        self.file_name = file_name
        self.level_n = price_level.name
        self.level = price_level.value
        self.filtered_data = self._filter_data()

    def _filter_data(self):
        lines = self.data.split("\n")
        filtered_lines = []
        previous_value = None

        # Iterate over the lines
        for i in range(len(lines)):
            parts = lines[i].split(";")
            if len(parts) >= 4:
                if parts[self.level] != previous_value:
                    # Keep only the first and last part
                    filtered_lines.append(f"{parts[0]};{parts[self.level]}")
                    previous_value = parts[self.level]

        return "\n".join(filtered_lines)

    def dump(self):
        """Dumpe the filtered data to a file"""
        with open(f"{self.file_name}_{self.level_n}_data.txt", "w") as file:
            file.write(self.filtered_data)


@time_it
def clean_data():
    file_name = "NQ 6-8-09-24.Last.txt"
    file_name = "NQ 6-8-09-24.Last.txt"
    data = read_file_plain(file_name)

    data = DataCleaner(data, file_name)
    data.dump()


if __name__ == "__main__":
    clean_data()
