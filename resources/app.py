import argparse as _argparse
import os as _os
import json as _json

from model import OllamaClassifier
from retrieve_table import retrieve_table
from select_column import select_column

def app(parameters_path):
    parameters = _json.load(open(parameters_path, 'r', encoding='utf-8'))

    output = parameters['output']
    _os.makedirs(output, exist_ok=True)

    classification = parameters['sources']['classification']
    data = parameters['sources']['data']

    classification_path = retrieve_table(
        output, classification['report'], classification['table']
    )

    classification_column = select_column(
        classification_path, classification['column']
    )

    data_path = retrieve_table(
        output, data['report'], data['table']
    )

    data_column = select_column(
        data_path, data['column']
    )

    print(f"Processing files")
    classifier = OllamaClassifier(model=parameters['model'])
    classifier.process_files(
        categories=classification_column,
        values=data_column,
        output_file=_os.path.join(output, 'classified.csv')
    )

if __name__ == "__main__":
    parser = _argparse.ArgumentParser(description="Power BI Classifier Tool")
    parser.add_argument('--parameters', type=str, required=True, help='Path to JSON parameters file')
    args = parser.parse_args()
    app(parameters_path=args.parameters)