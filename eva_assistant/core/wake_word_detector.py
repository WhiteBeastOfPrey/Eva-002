"""
Модуль для постоянного асинхронного распознавания wake-word "ЕВА"
"""

import asyncio
import logging
import threading
import time
import wave
from typing import Callable, Optional, List
import sounddevice as sd
import numpy as np
from fuzzywuzzy import fuzz
import speech_recognition as sr

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Детектор wake-word с постоянным прослушиванием"""
    
    def __init__(self, wake_words: List[str] = None, threshold: int = 65):
        self.wake_words = wake_words or ["ева", "eva", "эва"]
        self.threshold = threshold
        self.is_listening = False
        self.is_active = False
        self.callback: Optional[Callable] = None
        
        # Настройки аудио
        self.sample_rate = 16000
        self.chunk_duration = 1.0  # секунды
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        
        # Recognizer для оффлайн режима
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=self.sample_rate)
        
        # Буфер для аудио
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        
        # Поток для обработки
        self.processing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        logger.info(f"Wake word detector initialized with words: {self.wake_words}")
    
    def set_callback(self, callback: Callable):
        """Установить callback для срабатывания wake-word"""
        self.callback = callback
    
    async def start_listening(self):
        """Начать постоянное прослушивание wake-word"""
        if self.is_listening:
            logger.warning("Wake word detector is already listening")
            return
        
        self.is_listening = True
        self.stop_event.clear()
        
        # Калибровка микрофона
        await self._calibrate_microphone()
        
        # Запуск потока обработки
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        
        # Запуск записи аудио
        asyncio.create_task(self._audio_recording_loop())
        
        logger.info("Wake word detector started listening")
    
    async def stop_listening(self):
        """Остановить прослушивание"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        self.stop_event.set()
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        logger.info("Wake word detector stopped listening")
    
    async def _calibrate_microphone(self):
        """Калибровка микрофона для подавления шума"""
        try:
            logger.info("Calibrating microphone for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Microphone calibration completed")
        except Exception as e:
            logger.error(f"Failed to calibrate microphone: {e}")
    
    async def _audio_recording_loop(self):
        """Основной цикл записи аудио"""
        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            # Добавляем данные в буфер
            with self.buffer_lock:
                self.audio_buffer.extend(indata[:, 0])  # Моно канал
                
                # Ограничиваем размер буфера
                if len(self.audio_buffer) > self.chunk_size * 3:
                    self.audio_buffer = self.audio_buffer[-self.chunk_size * 2:]
        
        try:
            with sd.InputStream(
                callback=audio_callback,
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                blocksize=1024
            ):
                while self.is_listening and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Audio recording error: {e}")
            self.is_listening = False
    
    def _processing_loop(self):
        """Цикл обработки аудио данных"""
        while self.is_listening and not self.stop_event.is_set():
            try:
                # Получаем данные из буфера
                with self.buffer_lock:
                    if len(self.audio_buffer) < self.chunk_size:
                        time.sleep(0.1)
                        continue
                    
                    # Берем чанк для обработки
                    audio_chunk = np.array(self.audio_buffer[:self.chunk_size])
                    self.audio_buffer = self.audio_buffer[self.chunk_size//2:]  # Перекрытие 50%
                
                # Проверяем уровень звука
                if not self._is_speech_detected(audio_chunk):
                    continue
                
                # Распознаем речь
                text = self._recognize_speech(audio_chunk)
                if text:
                    # Проверяем на wake-word
                    if self._check_wake_word(text):
                        logger.info(f"Wake word detected: '{text}'")
                        if self.callback:
                            # Вызываем callback в основном потоке
                            asyncio.run_coroutine_threadsafe(
                                self._trigger_callback(text),
                                asyncio.get_event_loop()
                            )
            
            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                time.sleep(0.5)
    
    def _is_speech_detected(self, audio_chunk: np.ndarray) -> bool:
        """Определить, содержит ли аудио речь"""
        # Простая проверка по уровню звука и частотным характеристикам
        rms = np.sqrt(np.mean(audio_chunk**2))
        return rms > 0.01  # Пороговое значение
    
    def _recognize_speech(self, audio_chunk: np.ndarray) -> Optional[str]:
        """Распознать речь из аудио чанка"""
        try:
            # Конвертируем в формат для speech_recognition
            audio_data = (audio_chunk * 32767).astype(np.int16)
            
            # Создаем AudioData объект
            audio = sr.AudioData(
                audio_data.tobytes(),
                self.sample_rate,
                2  # 16-bit
            )
            
            # Пытаемся распознать с помощью разных движков
            try:
                # Сначала пытаемся Google (онлайн)
                text = self.recognizer.recognize_google(audio, language='ru-RU')
                return text.lower().strip()
            except (sr.UnknownValueError, sr.RequestError):
                pass
            
            try:
                # Fallback на Sphinx (оффлайн)
                text = self.recognizer.recognize_sphinx(audio, language='ru-RU')
                return text.lower().strip()
            except (sr.UnknownValueError, sr.RequestError):
                pass
            
        except Exception as e:
            logger.debug(f"Speech recognition error: {e}")
        
        return None
    
    def _check_wake_word(self, text: str) -> bool:
        """Проверить, содержит ли текст wake-word"""
        if not text:
            return False
        
        text_words = text.split()
        
        for word in text_words:
            for wake_word in self.wake_words:
                # Используем fuzzywuzzy для нечеткого сравнения
                similarity = fuzz.ratio(word, wake_word)
                if similarity >= self.threshold:
                    logger.debug(f"Wake word match: '{word}' -> '{wake_word}' ({similarity}%)")
                    return True
        
        return False
    
    async def _trigger_callback(self, detected_text: str):
        """Вызвать callback при обнаружении wake-word"""
        if self.callback:
            try:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(detected_text)
                else:
                    self.callback(detected_text)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_status(self) -> dict:
        """Получить статус детектора"""
        return {
            "is_listening": self.is_listening,
            "is_active": self.is_active,
            "wake_words": self.wake_words,
            "threshold": self.threshold,
            "buffer_size": len(self.audio_buffer)
        }