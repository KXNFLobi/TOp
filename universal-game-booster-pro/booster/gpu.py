"""Read-only driver/performance-counter sources. No hooks, injection or fabricated sensors."""
from collections import defaultdict
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from .windows import IS_WINDOWS, NO_WINDOW

def aggregate_engines(counters):
    engines=defaultdict(float)
    for counter in counters:
        name=str(counter.get("Name",""))
        match=re.fullmatch(r"pid_\d+_(luid_.+_phys_\d+_eng_\d+_engtype_.+)",name,re.I)
        if not match:continue
        try:value=float(counter["UtilizationPercentage"])
        except (TypeError,ValueError,KeyError):continue
        if 0<=value<=100:engines[match[1]]+=value
    return min(100,max(engines.values())) if engines else None

def probe_gpu():
    smi=shutil.which("nvidia-smi")
    if smi:
        try:
            result=subprocess.run([smi,"--query-gpu=utilization.gpu,temperature.gpu","--format=csv,noheader,nounits"],capture_output=True,timeout=3,creationflags=NO_WINDOW)
            pairs=[line.split(",") for line in result.stdout.decode().splitlines()]
            if result.returncode==0 and pairs:
                def numeric(values):
                    found=[]
                    for value in values:
                        try:found.append(float(value))
                        except (ValueError,TypeError):pass
                    return found
                utilization=[v for v in numeric(p[0] for p in pairs) if 0<=v<=100]
                temperatures=[v for v in numeric(p[1] for p in pairs if len(p)>1) if -20<=v<=150]
                if utilization:return max(utilization),max(temperatures) if temperatures else None,"NVIDIA · máximo entre GPUs"
        except (OSError,ValueError,subprocess.SubprocessError):pass
    if IS_WINDOWS:
        try:
            script=("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
                    "@(Get-CimInstance -ClassName Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | "
                    "Select-Object Name,UtilizationPercentage) | ConvertTo-Json -Compress")
            powershell=str(Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32/WindowsPowerShell/v1.0/powershell.exe")
            result=subprocess.run([powershell,"-NoProfile","-NonInteractive","-EncodedCommand",base64.b64encode(script.encode("utf-16le")).decode()],capture_output=True,timeout=8,creationflags=NO_WINDOW)
            data=json.loads(result.stdout.decode("utf-8-sig")) if result.returncode==0 else []
            if isinstance(data,dict):data=[data]
            value=aggregate_engines(data)
            if value is not None:return value,None,"Windows · motor GPU mais ocupado"
        except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):pass
    return None,None,"Indisponível"
