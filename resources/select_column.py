import csv
from typing import List

def select_column(csv_path: str, column_name: str) -> List[str]:
    """
    Extract a single column from a CSV file by column name.
    
    Args:
        csv_path: Path to the input CSV file
        column_name: Name of the column to extract
        
    Returns:
        List of values from the specified column (without header)
        
    Raises:
        ValueError: If the column name is not found in the CSV header
    """
    with open(csv_path, 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        # Check if column exists in the header
        if column_name not in reader.fieldnames:
            raise ValueError(f"Column '{column_name}' not found in CSV header")
        
        # Extract the specified column
        column_data = [row[column_name] for row in reader]
    
    return column_data