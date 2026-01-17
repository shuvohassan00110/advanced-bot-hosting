# -*- coding: utf-8 -*-
"""
Process hosting and management
"""

import os
import sys
import time
import asyncio
import subprocess
import psutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from config import (
    USERS_DIR, AUTO_RESTART_CHECK_INTERVAL, 
    AUTO_RESTART_BACKOFF_SEC, LOGS_DIR
)
from database import get_project, stat_increment

@dataclass
class RunningProcess:
    """Running process information"""
    user_id: int
    project_id: int
    entry_file: str
    language: str
    process: subprocess.Popen
    start_time: datetime
    log_path: Path
    auto_restart: bool
    restart_count: int = 0
    last_exit_code: Optional[int] = None
    backoff_until: float = 0.0

# Global dict of running processes
running_processes: Dict[str, RunningProcess] = {}

def make_key(user_id: int, project_id: int) -> str:
    """Create unique key for process"""
    return f"{user_id}:{project_id}"

def get_project_root(user_id: int, project_id: int) -> Path:
    """Get project directory path"""
    path = USERS_DIR / str(user_id) / f"project_{project_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_venv_path(user_id: int, project_id: int) -> Path:
    """Get virtual environment path"""
    return get_project_root(user_id, project_id) / ".venv"

def get_python_executable(user_id: int, project_id: int) -> Path:
    """Get Python executable (venv or system)"""
    venv = get_venv_path(user_id, project_id)
    if venv.exists():
        if os.name == 'nt':
            return venv / "Scripts" / "python.exe"
        return venv / "bin" / "python"
    return Path(sys.executable)

def get_pip_executable(user_id: int, project_id: int) -> Path:
    """Get pip executable"""
    venv = get_venv_path(user_id, project_id)
    if venv.exists():
        if os.name == 'nt':
            return venv / "Scripts" / "pip.exe"
        return venv / "bin" / "pip"
    return Path(sys.executable).parent / "pip"

def get_log_path(user_id: int, project_id: int) -> Path:
    """Get log file path"""
    log_dir = LOGS_DIR / str(user_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"project_{project_id}.log"

def create_venv(user_id: int, project_id: int) -> Tuple[bool, str]:
    """Create virtual environment"""
    venv_path = get_venv_path(user_id, project_id)
    
    if venv_path.exists():
        return True, "Virtual environment already exists"
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return True, "✅ Virtual environment created"
        else:
            return False, f"❌ Failed to create venv:\n{result.stderr}"
    
    except Exception as e:
        return False, f"❌ Error creating venv: {e}"

def install_requirements(user_id: int, project_id: int) -> Tuple[bool, str]:
    """Install requirements.txt"""
    project_root = get_project_root(user_id, project_id)
    req_file = project_root / "requirements.txt"
    
    if not req_file.exists():
        return False, "❌ requirements.txt not found"
    
    # Ensure venv exists
    venv_ok, venv_msg = create_venv(user_id, project_id)
    if not venv_ok:
        return False, venv_msg
    
    pip_path = get_pip_executable(user_id, project_id)
    
    try:
        result = subprocess.run(
            [str(pip_path), "install", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            return True, f"✅ Dependencies installed successfully!\n\n{result.stdout[-500:]}"
        else:
            return False, f"❌ Installation failed:\n\n{result.stderr[-1000:]}"
    
    except subprocess.TimeoutExpired:
        return False, "❌ Installation timeout (>5 minutes)"
    except Exception as e:
        return False, f"❌ Installation error: {e}"

def install_package(user_id: int, project_id: int, package_name: str) -> Tuple[bool, str]:
    """Install single package"""
    # Ensure venv exists
    venv_ok, venv_msg = create_venv(user_id, project_id)
    if not venv_ok:
        return False, venv_msg
    
    pip_path = get_pip_executable(user_id, project_id)
    
    try:
        result = subprocess.run(
            [str(pip_path), "install", package_name],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        if result.returncode == 0:
            # Get installed version
            version_result = subprocess.run(
                [str(pip_path), "show", package_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            version = "unknown"
            if version_result.returncode == 0:
                for line in version_result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        version = line.split(':', 1)[1].strip()
                        break
            
            return True, f"✅ Installed {package_name} v{version}"
        else:
            return False, f"❌ Failed to install:\n{result.stderr[-500:]}"
    
    except subprocess.TimeoutExpired:
        return False, "❌ Installation timeout"
    except Exception as e:
        return False, f"❌ Error: {e}"

def start_process(user_id: int, project_id: int) -> Tuple[bool, str]:
    """Start a project process"""
    key = make_key(user_id, project_id)
    
    # Check if already running
    if key in running_processes:
        proc = running_processes[key]
        if proc.process.poll() is None:
            return False, "❌ Project is already running"
    
    # Get project info
    project = get_project(user_id, project_id)
    if not project:
        return False, "❌ Project not found"
    
    _, name, entry, lang, auto_restart, desc, _ = project
    
    if not entry or not lang:
        return False, "❌ Entry file or language not configured.\nUse ⚙️ Settings to configure."
    
    project_root = get_project_root(user_id, project_id)
    entry_path = project_root / entry
    
    if not entry_path.exists():
        return False, f"❌ Entry file not found: {entry}"
    
    # Open log file
    log_path = get_log_path(user_id, project_id)
    log_file = open(log_path, 'a', encoding='utf-8', errors='replace')
    log_file.write(f"\n{'='*60}\n")
    log_file.write(f"Started at: {datetime.now()}\n")
    log_file.write(f"{'='*60}\n\n")
    log_file.flush()
    
    try:
        # Prepare command
        if lang == 'py':
            python_path = get_python_executable(user_id, project_id)
            cmd = [str(python_path), str(entry_path)]
        elif lang == 'js':
            cmd = ['node', str(entry_path)]
        else:
            log_file.close()
            return False, f"❌ Unsupported language: {lang}"
        
        # Start process
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=log_file,
            stderr=log_file,
            text=True
        )
        
        # Store process info
        running_processes[key] = RunningProcess(
            user_id=user_id,
            project_id=project_id,
            entry_file=entry,
            language=lang,
            process=process,
            start_time=datetime.now(),
            log_path=log_path,
            auto_restart=bool(auto_restart)
        )
        
        stat_increment('total_runs')
        
        return True, f"✅ <b>Started Successfully!</b>\n\n📦 Project: <b>{name}</b>\n🆔 PID: <code>{process.pid}</code>"
    
    except Exception as e:
        try:
            log_file.write(f"\n❌ Start error: {e}\n")
        except:
            pass
        log_file.close()
        return False, f"❌ Failed to start: {e}"

def stop_process(user_id: int, project_id: int) -> Tuple[bool, str]:
    """Stop a running process"""
    key = make_key(user_id, project_id)
    
    if key not in running_processes:
        return False, "❌ Process is not running"
    
    proc_info = running_processes[key]
    process = proc_info.process
    
    try:
        # Check if already stopped
        if process.poll() is not None:
            del running_processes[key]
            return True, "✅ Process was already stopped"
        
        # Try to terminate gracefully
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        
        # Terminate children first
        for child in children:
            try:
                child.terminate()
            except:
                pass
        
        # Terminate parent
        try:
            parent.terminate()
        except:
            pass
        
        # Wait for termination
        try:
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            # Force kill if still alive
            for child in children:
                try:
                    child.kill()
                except:
                    pass
            try:
                parent.kill()
            except:
                pass
        
        del running_processes[key]
        return True, "✅ Process stopped"
    
    except Exception as e:
        return False, f"❌ Error stopping process: {e}"

def restart_process(user_id: int, project_id: int) -> Tuple[bool, str]:
    """Restart a process"""
    key = make_key(user_id, project_id)
    
    # Stop if running
    if key in running_processes:
        stop_ok, stop_msg = stop_process(user_id, project_id)
        if not stop_ok:
            return False, stop_msg
        
        # Wait a bit
        time.sleep(1)
    
    # Start again
    return start_process(user_id, project_id)

def get_process_stats(user_id: int, project_id: int) -> Optional[Dict]:
    """Get process statistics"""
    key = make_key(user_id, project_id)
    
    if key not in running_processes:
        return None
    
    proc_info = running_processes[key]
    process = proc_info.process
    
    if process.poll() is not None:
        return None
    
    try:
        ps = psutil.Process(process.pid)
        
        # Get CPU and memory
        cpu_percent = ps.cpu_percent(interval=0.1)
        mem_info = ps.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        
        # Calculate uptime
        uptime = datetime.now() - proc_info.start_time
        uptime_str = str(uptime).split('.')[0]
        
        return {
            'status': '🟢 Running',
            'pid': process.pid,
            'cpu': f"{cpu_percent:.1f}%",
            'memory': f"{mem_mb:.1f} MB",
            'uptime': uptime_str,
            'restarts': proc_info.restart_count
        }
    
    except:
        return None

def read_logs(user_id: int, project_id: int, lines: int = 50) -> str:
    """Read last N lines from log file"""
    log_path = get_log_path(user_id, project_id)
    
    if not log_path.exists():
        return "📝 No logs yet"
    
    try:
        with open(log_path, 'rb') as f:
            # Read from end
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 8192
            data = b''
            
            while size > 0 and data.count(b'\n') <= lines:
                read_size = min(block, size)
                size -= read_size
                f.seek(size)
                data = f.read(read_size) + data
        
        # Decode and get last lines
        text = data.decode(errors='replace')
        log_lines = text.splitlines()[-lines:]
        
        return '\n'.join(log_lines) if log_lines else "📝 Log is empty"
    
    except Exception as e:
        return f"❌ Error reading logs: {e}"

async def auto_restart_monitor():
    """Monitor and auto-restart crashed processes"""
    while True:
        try:
            for key, proc_info in list(running_processes.items()):
                exit_code = proc_info.process.poll()
                
                # Still running
                if exit_code is None:
                    continue
                
                # Process exited
                proc_info.last_exit_code = exit_code
                
                # Check if auto-restart enabled
                if not proc_info.auto_restart:
                    continue
                
                # Check backoff
                now = time.time()
                if now < proc_info.backoff_until:
                    continue
                
                # Increment restart count
                proc_info.restart_count += 1
                
                # Calculate backoff
                backoff = AUTO_RESTART_BACKOFF_SEC * min(10, proc_info.restart_count)
                proc_info.backoff_until = now + backoff
                
                print(f"⚠️ Auto-restart: {key} exited with code {exit_code}, restarting in {backoff}s...")
                
                # Wait backoff time
                await asyncio.sleep(backoff)
                
                # Remove from dict
                del running_processes[key]
                
                # Try to restart
                success, msg = start_process(proc_info.user_id, proc_info.project_id)
                
                if success:
                    stat_increment('total_restarts')
                    print(f"✅ Auto-restart successful: {key}")
                else:
                    print(f"❌ Auto-restart failed: {key} - {msg}")
        
        except Exception as e:
            print(f"❌ Auto-restart monitor error: {e}")
        
        await asyncio.sleep(AUTO_RESTART_CHECK_INTERVAL)

def get_all_running() -> list:
    """Get list of all running processes"""
    result = []
    for key, proc_info in running_processes.items():
        if proc_info.process.poll() is None:
            result.append({
                'key': key,
                'user_id': proc_info.user_id,
                'project_id': proc_info.project_id,
                'pid': proc_info.process.pid,
                'uptime': str(datetime.now() - proc_info.start_time).split('.')[0],
                'restarts': proc_info.restart_count
            })
    return result