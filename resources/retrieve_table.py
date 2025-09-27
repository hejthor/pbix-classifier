import subprocess as _subprocess
import os as _os

def retrieve_table(folder, report, table):

    result = _subprocess.run(
        f'dscmd export csv "{folder}" --server "{report}.pbix" --tables "{table}" --filetype "UTF8CSV"',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(
            "dscmd csv failed for table '" + table + f"'\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    
    return _os.path.join(folder, table + ".csv")