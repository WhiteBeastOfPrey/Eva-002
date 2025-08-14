"""
Движок распознавания речи с поддержкой оффлайн и онлайн режимов
"""

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Optional, Callable, Dict, Any
import speech_recognition as sr
import sounddevice as sd
import numpy as np
import json
import os

logger = logging.getLogger(__name__)


class RecognitionMode(Enum):
    """Режимы распознавания речи"""
    ONLINE = "online"
    OFFLINE = "offline"
    AUTO = "auto"


class SpeechEngine:
    """Движок распознавания речи"""
    
    def __init__(self, mode: RecognitionMode = RecognitionMode.AUTO):
        self.mode = mode
        self.is_listening = False
        self.is_recording = False
        
        # Настройки аудио
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_duration = 0.5
        self.silence_threshold = 0.01
        self.silence_duration = 1.5  # секунды тишины для завершения записи
        
        # Recognizer
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=self.sample_rate)
        
        # Буферы и потоки
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.recording_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None
        self.on_text_recognized: Optional[Callable] = None
        self.on_audio_level: Optional[Callable] = None
        
        # Инициализация
        self._initialize_recognizer()
        
        logger.info(f"Speech engine initialized in {mode.value} mode")
    
    def _initialize_recognizer(self):
        """Инициализация распознавателя"""
        try:
            # Калибровка микрофона
            logger.info("Calibrating microphone...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            # Настройки распознавателя
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            self.recognizer.phrase_threshold = 0.3
            
            logger.info("Speech recognizer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize speech recognizer: {e}")
    
    def set_callbacks(self, **callbacks):
        """Установить callback функции"""
        self.on_speech_start = callbacks.get('on_speech_start')
        self.on_speech_end = callbacks.get('on_speech_end')
        self.on_text_recognized = callbacks.get('on_text_recognized')
        self.on_audio_level = callbacks.get('on_audio_level')
    
    async def start_listening(self):
        """Начать прослушивание речи"""
        if self.is_listening:
            logger.warning("Speech engine is already listening")
            return
        
        self.is_listening = True
        self.stop_event.clear()
        
        # Запуск потока записи
        self.recording_thread = threading.Thread(
            target=self._recording_loop,
            daemon=True
        )
        self.recording_thread.start()
        
        logger.info("Speech engine started listening")
    
    async def stop_listening(self):
        """Остановить прослушивание"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        self.stop_event.set()
        
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        logger.info("Speech engine stopped listening")
    
    async def recognize_once(self, timeout: float = 5.0) -> Optional[str]:
        """Однократное распознавание речи с таймаутом"""
        logger.info("Starting single speech recognition...")
        
        try:
            # Ждем начала речи
            audio_data = await self._wait_for_speech(timeout)
            if not audio_data:
                logger.warning("No speech detected within timeout")
                return None
            
            # Распознаем текст
            text = await self._recognize_audio(audio_data)
            return text
            
        except Exception as e:
            logger.error(f"Single recognition error: {e}")
            return None
    
    async def _wait_for_speech(self, timeout: float) -> Optional[bytes]:
        """Ожидание и запись речи"""
        start_time = time.time()
        audio_data = []
        is_speaking = False
        silence_start = None
        
        def audio_callback(indata, frames, time_info, status):
            nonlocal is_speaking, silence_start
            
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            # Вычисляем уровень звука
            audio_level = np.sqrt(np.mean(indata**2))
            
            # Callback для уровня звука
            if self.on_audio_level:
                asyncio.run_coroutine_threadsafe(
                    self._call_callback(self.on_audio_level, audio_level),
                    asyncio.get_event_loop()
                )
            
            # Определяем речь
            if audio_level > self.silence_threshold:
                if not is_speaking:
                    is_speaking = True
                    silence_start = None
                    logger.debug("Speech started")
                    if self.on_speech_start:
                        asyncio.run_coroutine_threadsafe(
                            self._call_callback(self.on_speech_start),
                            asyncio.get_event_loop()
                        )
                
                audio_data.extend(indata[:, 0])
            else:
                if is_speaking:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > self.silence_duration:
                        is_speaking = False
                        logger.debug("Speech ended")
                        if self.on_speech_end:
                            asyncio.run_coroutine_threadsafe(
                                self._call_callback(self.on_speech_end),
                                asyncio.get_event_loop()
                            )
                        return  # Завершаем запись
        
        try:
            with sd.InputStream(
                callback=audio_callback,
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32
            ):
                while time.time() - start_time < timeout:
                    if not is_speaking and audio_data:
                        break
                    await asyncio.sleep(0.1)
            
            if audio_data:
                # Конвертируем в байты
                audio_array = np.array(audio_data, dtype=np.float32)
                audio_int16 = (audio_array * 32767).astype(np.int16)
                return audio_int16.tobytes()
            
        except Exception as e:
            logger.error(f"Audio recording error: {e}")
        
        return None
    
    def _recording_loop(self):
        """Основной цикл записи для постоянного прослушивания"""
        while self.is_listening and not self.stop_event.is_set():
            try:
                # Здесь можно реализовать постоянную запись
                # Пока что просто ждем
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Recording loop error: {e}")
                time.sleep(1.0)
    
    async def _recognize_audio(self, audio_data: bytes) -> Optional[str]:
        """Распознать аудио данные"""
        try:
            # Создаем AudioData объект
            audio = sr.AudioData(
                audio_data,
                self.sample_rate,
                2  # 16-bit
            )
            
            # Выбираем метод распознавания в зависимости от режима
            text = None
            
            if self.mode == RecognitionMode.ONLINE or self.mode == RecognitionMode.AUTO:
                text = await self._recognize_online(audio)
            
            if not text and (self.mode == RecognitionMode.OFFLINE or self.mode == RecognitionMode.AUTO):
                text = await self._recognize_offline(audio)
            
            if text and self.on_text_recognized:
                await self._call_callback(self.on_text_recognized, text)
            
            return text
            
        except Exception as e:
            logger.error(f"Audio recognition error: {e}")
            return None
    
    async def _recognize_online(self, audio: sr.AudioData) -> Optional[str]:
        """Онлайн распознавание речи"""
        try:
            # Google Speech Recognition
            text = self.recognizer.recognize_google(audio, language='ru-RU')
            logger.debug(f"Online recognition result: {text}")
            return text.lower().strip()
            
        except sr.UnknownValueError:
            logger.debug("Online recognition: could not understand audio")
        except sr.RequestError as e:
            logger.warning(f"Online recognition service error: {e}")
        except Exception as e:
            logger.error(f"Online recognition error: {e}")
        
        return None
    
    async def _recognize_offline(self, audio: sr.AudioData) -> Optional[str]:
        """Оффлайн распознавание речи"""
        try:
            # Sphinx (PocketSphinx)
            text = self.recognizer.recognize_sphinx(audio, language='ru-RU')
            logger.debug(f"Offline recognition result: {text}")
            return text.lower().strip()
            
        except sr.UnknownValueError:
            logger.debug("Offline recognition: could not understand audio")
        except sr.RequestError as e:
            logger.warning(f"Offline recognition error: {e}")
        except Exception as e:
            logger.error(f"Offline recognition error: {e}")
        
        return None
    
    async def _call_callback(self, callback: Callable, *args):
        """Безопасный вызов callback функции"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def set_mode(self, mode: RecognitionMode):
        """Изменить режим распознавания"""
        self.mode = mode
        logger.info(f"Speech recognition mode changed to: {mode.value}")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус движка"""
        return {
            "mode": self.mode.value,
            "is_listening": self.is_listening,
            "is_recording": self.is_recording,
            "sample_rate": self.sample_rate,
            "energy_threshold": self.recognizer.energy_threshold
        }
    
    def get_audio_devices(self) -> Dict[str, Any]:
        """Получить список аудио устройств"""
        try:
            devices = sd.query_devices()
            input_devices = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate']
                    })
            
            return {
                'default_device': sd.default.device[0],
                'input_devices': input_devices
            }
            
        except Exception as e:
            logger.error(f"Failed to get audio devices: {e}")
            return {'input_devices': []}