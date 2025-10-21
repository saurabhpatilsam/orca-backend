import pandas as pd


def merge_files(file1, file2):

    # Step 1: Read the two CSV files
    df1 = pd.read_csv(f"output/{file1}")
    df2 = pd.read_csv(f"output/{file2}")

    # Step 2: Merge the two DataFrames (concatenate them)
    merged_df = pd.concat([df1, df2])

    # Step 3: Sort the merged DataFrame by the 'A_time' column
    sorted_df = merged_df.sort_values(by="A_time")

    # Step 4: Save the sorted DataFrame to a new CSV file
    sorted_df.to_csv("merged_sorted_file.csv", index=False)

    print("CSV files merged and sorted by 'A_time' column successfully.")


if __name__ == "__main__":
    merge_files(
        "Amer_long_20_7_20240815_102601.csv", "Amer_short_7_20_20240815_102517.csv"
    )
