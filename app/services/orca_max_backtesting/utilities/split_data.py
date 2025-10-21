import datetime

from app.services.orca_max_backtesting.helper import get_price_time, read_file_plain
from app.utils.decorators.timing.time import time_it


class DataCleaner:
    def __init__(self, data, file_name, time_from, time_to=None):
        self.data = data
        self.file_name = file_name
        self.time_from = time_from
        self.time_to = time_to if time_to else datetime.datetime(2300, 1, 1, 0, 0, 0)
        self.filtered_data = self._filter_data()

    def _filter_data(self):
        lines = self.data.split("\n")
        filtered_lines = []
        # Iterate over the lines
        for i in range(len(lines)):
            parts = lines[i].split(";")
            if len(parts) >= 4:
                if (
                    get_price_time(parts[0]) >= self.time_from
                    and get_price_time(parts[0]) <= self.time_to
                ):
                    # Keep only the first and last part
                    filtered_lines.append(lines[i])

        return "\n".join(filtered_lines)

    def dump(self):
        """Dumpe the filtered data to a file"""
        file_name = f"{self.file_name}_timed_data.txt"
        with open(file_name, "w") as file:
            file.write(self.filtered_data)
        print(file_name + " created")


@time_it
def clean_data(file_name, time_from: str, time_to: str = None):
    # time = datetime.datetime(2024, 8, 8, 5, 0)
    _time_from = datetime.datetime.strptime(time_from, "%Y-%m-%d %H:%M:%S")
    _time_to = (
        datetime.datetime.strptime(time_to, "%Y-%m-%d %H:%M:%S") if time_to else None
    )

    # file_name = "NQ 6-8-09-24.Last.txt"
    data = read_file_plain(file_name)

    data = DataCleaner(data, file_name, _time_from, _time_to)
    data.dump()


if __name__ == "__main__":
    time_from = "2024-08-29 05:00:00"
    # time_to = "2024-08-08 05:00:00"
    time_to = None

    file_name = "NQ-29-30--08 09-24.Last.txt"
    clean_data(file_name, time_from, time_to)
