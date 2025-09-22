import re
import subprocess as _subprocess

def pbix_port():
    """Find the Power BI Desktop port by parsing netstat output on Windows.

    Power BI Desktop often connects to a fixed localhost port (foreign address)
    using many ephemeral local ports, so we detect the most common foreign port
    among ESTABLISHED connections owned by PBIDesktop.exe.
    """
    commands = [
        'netstat -bno',  # includes owning executable (requires admin)
        'netstat -ano',  # fallback: resolve via PID -> tasklist
    ]
    ports_counter = {}
    last_program = None

    def incr(port: int):
        ports_counter[port] = ports_counter.get(port, 0) + 1

    for cmd in commands:
        try:
            res = _subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if res.returncode != 0 or not res.stdout:
                continue
            last_program = None
            for raw_line in res.stdout.splitlines():
                line = raw_line.strip()
                # Program line like: [PBIDesktop.exe]
                m_prog = re.match(r'^\[(.+?)\]$', line)
                if m_prog:
                    last_program = m_prog.group(1)
                    continue
                if not line.upper().startswith('TCP'):
                    continue
                parts = re.split(r'\s+', line)
                if len(parts) < 5:
                    continue
                # parts: proto, local, foreign, state, pid
                local_addr, foreign_addr, state, pid = parts[1], parts[2], parts[3].upper(), parts[4]
                if state != 'ESTABLISHED':
                    continue
                # Only consider localhost to localhost
                def is_loopback(addr: str) -> bool:
                    return addr.startswith('127.0.0.1:') or addr.startswith('[::1]:')

                if not (is_loopback(local_addr) and is_loopback(foreign_addr)):
                    continue

                # Determine if this row belongs to PBIDesktop
                is_pbi = False
                if ' -bno' in cmd and last_program:
                    is_pbi = 'pbidesktop' in last_program.lower()
                else:
                    # Resolve PID -> image name via tasklist
                    try:
                        task_cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
                        task = _subprocess.run(task_cmd, capture_output=True, text=True, shell=True)
                        if task.returncode == 0 and task.stdout:
                            first_line = task.stdout.splitlines()[0].strip()
                            if first_line:
                                image_name = first_line.split(',')[0].strip().strip('"')
                                is_pbi = image_name.lower().startswith('pbidesktop')
                    except Exception:
                        pass

                if not is_pbi:
                    continue

                # Extract foreign port (the fixed service port)
                try:
                    foreign_port = int(foreign_addr.rsplit(':', 1)[-1].strip(']'))
                    incr(foreign_port)
                except ValueError:
                    continue

            # If we found any ports on this pass, choose the most frequent
            if ports_counter:
                return max(ports_counter.items(), key=lambda kv: kv[1])[0]
        except Exception:
            continue

    raise RuntimeError("Could not find Power BI Desktop port. Please ensure Power BI Desktop is running with an open report.")
