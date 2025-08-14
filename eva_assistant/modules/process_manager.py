"""
Модуль для работы с активными процессами
"""

import asyncio
import logging
import psutil
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """Состояния процесса"""
    RUNNING = "running"
    SLEEPING = "sleeping"
    DISK_SLEEP = "disk-sleep"
    STOPPED = "stopped"
    TRACING_STOP = "tracing-stop"
    ZOMBIE = "zombie"
    DEAD = "dead"
    WAKE_KILL = "wake-kill"
    WAKING = "waking"
    IDLE = "idle"
    LOCKED = "locked"
    WAITING = "waiting"
    SUSPENDED = "suspended"


@dataclass
class ProcessInfo:
    """Информация о процессе"""
    pid: int
    name: str
    exe_path: str
    status: ProcessState
    cpu_percent: float
    memory_percent: float
    memory_info: Dict[str, int]
    create_time: float
    num_threads: int
    is_foreground: bool = False
    window_title: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            'pid': self.pid,
            'name': self.name,
            'exe_path': self.exe_path,
            'status': self.status.value,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_info': self.memory_info,
            'create_time': self.create_time,
            'num_threads': self.num_threads,
            'is_foreground': self.is_foreground,
            'window_title': self.window_title
        }


class ProcessManager:
    """Менеджер для работы с процессами"""
    
    def __init__(self, update_interval: float = 1.0):
        self.update_interval = update_interval
        self.processes: Dict[int, ProcessInfo] = {}
        self.active_process: Optional[ProcessInfo] = None
        
        # Callbacks
        self.on_process_started: Optional[Callable] = None
        self.on_process_ended: Optional[Callable] = None
        self.on_active_process_changed: Optional[Callable] = None
        
        # Мониторинг
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Фильтры
        self.excluded_processes = {
            'System Idle Process', 'System', 'Registry', 'smss.exe',
            'csrss.exe', 'wininit.exe', 'winlogon.exe', 'services.exe',
            'lsass.exe', 'svchost.exe', 'dwm.exe', 'explorer.exe'
        }
        
        logger.info("Process manager initialized")
    
    async def start_monitoring(self):
        """Начать мониторинг процессов"""
        if self.is_monitoring:
            logger.warning("Process monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Process monitoring started")
    
    async def stop_monitoring(self):
        """Остановить мониторинг процессов"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Process monitoring stopped")
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while self.is_monitoring:
            try:
                await self._update_processes()
                await self._detect_active_process()
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def _update_processes(self):
        """Обновить список процессов"""
        current_pids = set()
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'status', 'cpu_percent', 
                                           'memory_percent', 'memory_info', 'create_time', 'num_threads']):
                try:
                    proc_info = proc.info
                    pid = proc_info['pid']
                    current_pids.add(pid)
                    
                    # Пропускаем системные процессы
                    if proc_info['name'] in self.excluded_processes:
                        continue
                    
                    # Создаем или обновляем информацию о процессе
                    process_info = ProcessInfo(
                        pid=pid,
                        name=proc_info['name'],
                        exe_path=proc_info.get('exe', ''),
                        status=ProcessState(proc_info['status']),
                        cpu_percent=proc_info.get('cpu_percent', 0.0),
                        memory_percent=proc_info.get('memory_percent', 0.0),
                        memory_info=proc_info.get('memory_info', {})._asdict() if proc_info.get('memory_info') else {},
                        create_time=proc_info.get('create_time', 0.0),
                        num_threads=proc_info.get('num_threads', 0)
                    )
                    
                    # Проверяем, новый ли это процесс
                    if pid not in self.processes:
                        if self.on_process_started:
                            await self._call_callback(self.on_process_started, process_info)
                    
                    self.processes[pid] = process_info
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        
        except Exception as e:
            logger.error(f"Error updating processes: {e}")
        
        # Удаляем завершившиеся процессы
        finished_pids = set(self.processes.keys()) - current_pids
        for pid in finished_pids:
            process_info = self.processes.pop(pid, None)
            if process_info and self.on_process_ended:
                await self._call_callback(self.on_process_ended, process_info)
    
    async def _detect_active_process(self):
        """Определить активный процесс"""
        try:
            # Пытаемся определить активное окно (зависит от платформы)
            active_window_pid = await self._get_active_window_pid()
            
            if active_window_pid and active_window_pid in self.processes:
                new_active = self.processes[active_window_pid]
                new_active.is_foreground = True
                
                # Сбрасываем флаг у предыдущего активного процесса
                if self.active_process and self.active_process.pid != active_window_pid:
                    if self.active_process.pid in self.processes:
                        self.processes[self.active_process.pid].is_foreground = False
                
                # Уведомляем об изменении активного процесса
                if not self.active_process or self.active_process.pid != active_window_pid:
                    self.active_process = new_active
                    if self.on_active_process_changed:
                        await self._call_callback(self.on_active_process_changed, new_active)
        
        except Exception as e:
            logger.debug(f"Error detecting active process: {e}")
    
    async def _get_active_window_pid(self) -> Optional[int]:
        """Получить PID активного окна (зависит от платформы)"""
        try:
            import platform
            system = platform.system().lower()
            
            if system == "windows":
                return await self._get_active_window_pid_windows()
            elif system == "darwin":  # macOS
                return await self._get_active_window_pid_macos()
            elif system == "linux":
                return await self._get_active_window_pid_linux()
            
        except Exception as e:
            logger.debug(f"Error getting active window PID: {e}")
        
        return None
    
    async def _get_active_window_pid_windows(self) -> Optional[int]:
        """Получить PID активного окна в Windows"""
        try:
            import ctypes
            from ctypes import wintypes
            
            # Получаем handle активного окна
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return None
            
            # Получаем PID процесса окна
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            return pid.value if pid.value else None
            
        except Exception as e:
            logger.debug(f"Error getting Windows active window PID: {e}")
            return None
    
    async def _get_active_window_pid_macos(self) -> Optional[int]:
        """Получить PID активного окна в macOS"""
        try:
            import subprocess
            
            # Используем AppleScript для получения активного приложения
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                return unix id of frontApp
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                return int(result.stdout.strip())
                
        except Exception as e:
            logger.debug(f"Error getting macOS active window PID: {e}")
        
        return None
    
    async def _get_active_window_pid_linux(self) -> Optional[int]:
        """Получить PID активного окна в Linux"""
        try:
            import subprocess
            
            # Используем xdotool для получения активного окна
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowpid'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                return int(result.stdout.strip())
                
        except Exception as e:
            logger.debug(f"Error getting Linux active window PID: {e}")
        
        return None
    
    def get_processes(self, filter_criteria: Dict[str, Any] = None) -> List[ProcessInfo]:
        """
        Получить список процессов с фильтрацией
        
        Args:
            filter_criteria: Критерии фильтрации (name, status, min_cpu, min_memory)
        
        Returns:
            Отфильтрованный список процессов
        """
        processes = list(self.processes.values())
        
        if not filter_criteria:
            return processes
        
        filtered = []
        for proc in processes:
            match = True
            
            # Фильтр по имени
            if 'name' in filter_criteria:
                if filter_criteria['name'].lower() not in proc.name.lower():
                    match = False
            
            # Фильтр по статусу
            if 'status' in filter_criteria:
                if proc.status != ProcessState(filter_criteria['status']):
                    match = False
            
            # Фильтр по минимальному CPU
            if 'min_cpu' in filter_criteria:
                if proc.cpu_percent < filter_criteria['min_cpu']:
                    match = False
            
            # Фильтр по минимальной памяти
            if 'min_memory' in filter_criteria:
                if proc.memory_percent < filter_criteria['min_memory']:
                    match = False
            
            if match:
                filtered.append(proc)
        
        return filtered
    
    def get_process_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """Получить процесс по PID"""
        return self.processes.get(pid)
    
    def get_process_by_name(self, name: str) -> List[ProcessInfo]:
        """Получить процессы по имени"""
        return [proc for proc in self.processes.values() 
                if name.lower() in proc.name.lower()]
    
    def get_active_process(self) -> Optional[ProcessInfo]:
        """Получить активный процесс"""
        return self.active_process
    
    async def kill_process(self, pid: int, force: bool = False) -> bool:
        """
        Завершить процесс
        
        Args:
            pid: PID процесса
            force: Принудительное завершение
        
        Returns:
            True если процесс завершен успешно
        """
        try:
            proc = psutil.Process(pid)
            
            if force:
                proc.kill()  # SIGKILL
            else:
                proc.terminate()  # SIGTERM
            
            # Ждем завершения
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                if not force:
                    # Принудительное завершение если обычное не сработало
                    proc.kill()
                    proc.wait(timeout=3)
            
            logger.info(f"Process {pid} terminated successfully")
            return True
            
        except psutil.NoSuchProcess:
            logger.warning(f"Process {pid} does not exist")
            return True  # Процесс уже не существует
        except psutil.AccessDenied:
            logger.error(f"Access denied to terminate process {pid}")
            return False
        except Exception as e:
            logger.error(f"Error terminating process {pid}: {e}")
            return False
    
    async def suspend_process(self, pid: int) -> bool:
        """Приостановить процесс"""
        try:
            proc = psutil.Process(pid)
            proc.suspend()
            logger.info(f"Process {pid} suspended")
            return True
        except Exception as e:
            logger.error(f"Error suspending process {pid}: {e}")
            return False
    
    async def resume_process(self, pid: int) -> bool:
        """Возобновить процесс"""
        try:
            proc = psutil.Process(pid)
            proc.resume()
            logger.info(f"Process {pid} resumed")
            return True
        except Exception as e:
            logger.error(f"Error resuming process {pid}: {e}")
            return False
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'process_count': len(self.processes),
                'active_process': self.active_process.name if self.active_process else None
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def set_callbacks(self, **callbacks):
        """Установить callback функции"""
        self.on_process_started = callbacks.get('on_process_started')
        self.on_process_ended = callbacks.get('on_process_ended') 
        self.on_active_process_changed = callbacks.get('on_active_process_changed')
    
    async def _call_callback(self, callback: Callable, *args):
        """Безопасный вызов callback функции"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус менеджера процессов"""
        return {
            'is_monitoring': self.is_monitoring,
            'update_interval': self.update_interval,
            'process_count': len(self.processes),
            'active_process': self.active_process.to_dict() if self.active_process else None,
            'excluded_processes': list(self.excluded_processes)
        }