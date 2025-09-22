import re
import os as _os
import subprocess as _subprocess

def pbix_guid(port: int) -> str:
    """Try to discover the Power BI database (ID/GUID) on the given localhost port using dscmd.

    We attempt a couple of listing commands and parse for either a GUID or a
    database named "Model". Falls back to the literal name "Model" if discovery fails.
    """
    server = f"localhost:{port}"

    # 1) Try to find by inspecting Power BI Desktop workspace folders
    guid_candidates = []
    try:
        roots = [
            _os.path.join(_os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Power BI Desktop', 'AnalysisServicesWorkspaces'),
            _os.path.join(_os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Power BI Desktop Store', 'AnalysisServicesWorkspaces'),
        ]
        roots = [p for p in roots if p and _os.path.isdir(p)]
        print(f"[dax] Workspace discovery roots: {roots}")
        guid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        for base_dir in roots:
            for dirpath, dirnames, filenames in _os.walk(base_dir):
                if 'msmdsrv.port.txt' in filenames:
                    port_file = _os.path.join(dirpath, 'msmdsrv.port.txt')
                    try:
                        # Read as binary first to handle UTF-16/NUL bytes reliably
                        try:
                            with open(port_file, 'rb') as fb:
                                b = fb.read()
                            print(f"[dax] Read port file bytes: {len(b)} bytes")
                            digits = [chr(x) for x in b if 48 <= x <= 57]
                            content = ''.join(digits)
                        except Exception as e:
                            print(f"[dax] Binary read failed ({e}), falling back to text decoding")
                            try:
                                with open(port_file, 'r', encoding='utf-16', errors='ignore') as f:
                                    raw = f.read()
                            except Exception:
                                with open(port_file, 'r', encoding='utf-8', errors='ignore') as f:
                                    raw = f.read()
                            digits = re.findall(r"\d", raw)
                            content = ''.join(digits) if digits else raw.strip()
                        print(f"[dax] Found port file: {port_file} -> '{content}' (digits={digits[:10] if isinstance(digits, list) else 'n/a'})")
                        if content and str(port) == str(int(content)):
                            # Determine the correct Data directory.
                            # If the port file is under a folder named 'Data', use that folder directly.
                            candidates = []
                            base = _os.path.basename(dirpath).lower()
                            if base == 'data':
                                candidates.append(dirpath)
                            else:
                                candidates.extend([
                                    _os.path.join(dirpath, 'Data'),
                                    _os.path.join(_os.path.dirname(dirpath), 'Data'),
                                ])
                            for data_dir in candidates:
                                if _os.path.isdir(data_dir):
                                    print(f"[dax] Inspecting Data dir: {data_dir}")
                                    try:
                                        entries = _os.listdir(data_dir)
                                    except Exception as e:
                                        print(f"[dax] Unable to list Data dir '{data_dir}': {e}")
                                        entries = []
                                    print(f"[dax] Data dir entries ({len(entries)}): {entries[:20]}")
                                    for entry in entries:
                                        # Check pure GUID directory/file names or names containing GUIDs
                                        if guid_re.match(entry):
                                            print(f"[dax] Matched GUID from workspace: {entry}")
                                            guid_candidates.append(entry)
                                            continue
                                        m_guid = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", entry)
                                        if m_guid:
                                            guid = m_guid.group(0)
                                            print(f"[dax] Extracted GUID from entry '{entry}': {guid}")
                                            guid_candidates.append(guid)
                                    # If not found directly, look one level deeper in subdirs
                                    for entry in entries:
                                        sub = _os.path.join(data_dir, entry)
                                        if not _os.path.isdir(sub):
                                            continue
                                        try:
                                            sub_entries = _os.listdir(sub)
                                        except Exception as e:
                                            print(f"[dax] Unable to list subdir '{sub}': {e}")
                                            continue
                                        for se in sub_entries:
                                            if guid_re.match(se):
                                                print(f"[dax] Matched GUID in subdir '{sub}': {se}")
                                                guid_candidates.append(se)
                                                continue
                                            m_guid2 = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", se)
                                            if m_guid2:
                                                guid = m_guid2.group(0)
                                                print(f"[dax] Extracted GUID from sub-entry '{se}': {guid}")
                                                guid_candidates.append(guid)
                    except Exception as e:
                        print(f"[dax] Error reading port file '{port_file}': {e}")
    except Exception as e:
        print(f"[dax] Workspace discovery failed: {e}")

    # If we gathered workspace candidates, validate them with dscmd info
    if guid_candidates:
        tried = set()
        for guid in guid_candidates:
            if guid in tried:
                continue
            tried.add(guid)
            test_cmd = f'dscmd info --server "{server}" --database "{guid}"'
            print(f"[dax] Validating GUID via dscmd: {guid}")
            try:
                res = _subprocess.run(test_cmd, capture_output=True, text=True, shell=True)
                print(f"[dax] info exit={res.returncode}")
                if res.returncode == 0:
                    print(f"[dax] GUID validated: {guid}")
                    return guid
                else:
                    if res.stderr:
                        print(f"[dax] info STDERR: {res.stderr.strip()[:500]}")
                    if res.stdout:
                        print(f"[dax] info STDOUT (preview):\n{res.stdout.splitlines()[:10]}")
            except Exception as e:
                print(f"[dax] Exception validating GUID '{guid}': {e}")

        # If validation did not succeed (e.g., dscmd unavailable or lacks permission),
        # return the first discovered GUID as a best-effort fallback.
        if guid_candidates:
            print(f"[dax] Returning first discovered GUID without validation: {guid_candidates[0]}")
            return guid_candidates[0]

    candidates = [
        f'dscmd list databases --server "{server}"',
        f'dscmd databases --server "{server}"',
        f'dscmd info --server "{server}"',
    ]
    guid_re = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

    print(f"[dax.find_powerbi_database_id] Discovering database on {server}")
    for cmd in candidates:
        try:
            print(f"[dax] Running: {cmd}")
            res = _subprocess.run(cmd, capture_output=True, text=True, shell=True)
            print(f"[dax] Exit code: {res.returncode}")
            if res.returncode != 0:
                if res.stderr:
                    print(f"[dax] STDERR: {res.stderr.strip()[:500]}")
                continue
            out = (res.stdout or "") + "\n" + (res.stderr or "")
            if out.strip():
                preview = "\n".join(out.splitlines()[:10])
                print(f"[dax] Output preview:\n{preview}")
            # Prefer a line that mentions Model and contains a GUID
            for line in out.splitlines():
                if 'model' in line.lower():
                    m = guid_re.search(line)
                    if m:
                        print(f"[dax] Found GUID on Model line: {m.group(0)}")
                        return m.group(0)
            # Else, return the first GUID we see
            m_any = guid_re.search(out)
            if m_any:
                print(f"[dax] Found GUID anywhere in output: {m_any.group(0)}")
                return m_any.group(0)
        except Exception as e:
            print(f"[dax] Exception while running '{cmd}': {e}")
            continue

    # Fallback: many tools accept the friendly name "Model"
    print("[dax] Falling back to database name 'Model'")
    return "Model"
