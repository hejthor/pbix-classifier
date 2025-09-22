import subprocess as _subprocess
import os as _os

def pbix_table(folder, port, guid, table):
    
    server = f"localhost:{port}"
    database = guid

    result = _subprocess.run(
        f'dscmd export csv "{folder}" --server "{server}" --database "{database}" --tables "{table}" --filetype "UTF8CSV"',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(
            "dscmd csv failed for table '" + table + f"'\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    
    return _os.path.join(folder, table + ".csv")