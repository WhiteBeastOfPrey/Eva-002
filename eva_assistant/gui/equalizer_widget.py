"""
Виджет эквалайзера для индикации уровня аудио
"""

import random
import math
from typing import List
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient


class EqualizerWidget(QWidget):
    """Виджет эквалайзера для визуализации аудио уровней"""
    
    def __init__(self, parent=None, bars_count: int = 20):
        super().__init__(parent)
        
        self.bars_count = bars_count
        self.bar_values: List[float] = [0.0] * bars_count
        self.peak_values: List[float] = [0.0] * bars_count
        self.peak_decay: List[float] = [0.0] * bars_count
        
        # Настройки анимации
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(50)  # 20 FPS
        
        # Настройки внешнего вида
        self.bar_spacing = 2
        self.peak_hold_time = 30  # Время удержания пика (в кадрах)
        self.peak_decay_rate = 0.02
        self.smoothing_factor = 0.3
        
        # Цвета
        self.background_color = QColor(30, 30, 30)
        self.bar_colors = self._create_gradient_colors()
        self.peak_color = QColor(255, 255, 255, 200)
        self.border_color = QColor(60, 60, 60)
        
        # Текущий уровень аудио
        self.current_level = 0.0
        
        # Симуляция для демонстрации
        self.demo_mode = True
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._demo_update)
        self.demo_timer.start(100)
        
        self.setMinimumHeight(60)
        self.setMaximumHeight(120)
    
    def _create_gradient_colors(self) -> List[QColor]:
        """Создать градиентные цвета для полос"""
        colors = []
        
        for i in range(self.bars_count):
            # Создаем градиент от зеленого через желтый к красному
            ratio = i / (self.bars_count - 1)
            
            if ratio < 0.5:
                # Зеленый -> Желтый
                green_ratio = (0.5 - ratio) * 2
                yellow_ratio = ratio * 2
                color = QColor(
                    int(255 * yellow_ratio),
                    255,
                    0
                )
            else:
                # Желтый -> Красный
                yellow_ratio = (1.0 - ratio) * 2
                red_ratio = (ratio - 0.5) * 2
                color = QColor(
                    255,
                    int(255 * yellow_ratio),
                    0
                )
            
            colors.append(color)
        
        return colors
    
    def update_level(self, level: float):
        """
        Обновить уровень аудио
        
        Args:
            level: Уровень аудио (0.0 - 1.0)
        """
        self.demo_mode = False  # Отключаем демо режим при получении реальных данных
        self.current_level = max(0.0, min(1.0, level))
        self._update_bars_from_level()
    
    def _update_bars_from_level(self):
        """Обновить полосы на основе текущего уровня"""
        # Создаем спектр на основе уровня аудио
        for i in range(self.bars_count):
            # Имитируем частотный спектр
            frequency_weight = 1.0 - (abs(i - self.bars_count // 2) / (self.bars_count // 2))
            base_level = self.current_level * frequency_weight
            
            # Добавляем небольшую случайность для более реалистичного вида
            noise = random.uniform(-0.1, 0.1) * self.current_level
            target_value = max(0.0, min(1.0, base_level + noise))
            
            # Применяем сглаживание
            self.bar_values[i] = (
                self.bar_values[i] * (1.0 - self.smoothing_factor) +
                target_value * self.smoothing_factor
            )
    
    def _demo_update(self):
        """Обновление для демонстрационного режима"""
        if not self.demo_mode:
            return
        
        # Генерируем случайные значения для демонстрации
        for i in range(self.bars_count):
            # Создаем волнообразный паттерн
            time_factor = self.demo_timer.remainingTime() / 1000.0
            wave = math.sin(time_factor + i * 0.3) * 0.5 + 0.5
            noise = random.uniform(0.0, 0.3)
            
            target_value = wave * 0.7 + noise * 0.3
            target_value = max(0.0, min(1.0, target_value))
            
            # Применяем сглаживание
            self.bar_values[i] = (
                self.bar_values[i] * 0.8 +
                target_value * 0.2
            )
    
    def _update_animation(self):
        """Обновить анимацию (пики и затухание)"""
        for i in range(self.bars_count):
            current_value = self.bar_values[i]
            
            # Обновляем пики
            if current_value > self.peak_values[i]:
                self.peak_values[i] = current_value
                self.peak_decay[i] = self.peak_hold_time
            else:
                # Затухание пика
                if self.peak_decay[i] > 0:
                    self.peak_decay[i] -= 1
                else:
                    self.peak_values[i] -= self.peak_decay_rate
                    self.peak_values[i] = max(0.0, self.peak_values[i])
        
        self.update()  # Перерисовать виджет
    
    def paintEvent(self, event):
        """Отрисовка эквалайзера"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Заливаем фон
        painter.fillRect(self.rect(), self.background_color)
        
        # Рисуем рамку
        painter.setPen(QPen(self.border_color, 1))
        painter.drawRect(self.rect())
        
        if self.bars_count == 0:
            return
        
        # Вычисляем размеры полос
        widget_width = self.width() - 4  # Отступы по 2px с каждой стороны
        widget_height = self.height() - 4
        
        bar_width = (widget_width - (self.bars_count - 1) * self.bar_spacing) // self.bars_count
        bar_width = max(1, bar_width)  # Минимальная ширина полосы
        
        # Рисуем полосы
        for i in range(self.bars_count):
            x = 2 + i * (bar_width + self.bar_spacing)
            
            # Высота полосы на основе значения
            bar_height = int(widget_height * self.bar_values[i])
            y = self.height() - 2 - bar_height
            
            # Рисуем полосу
            if bar_height > 0:
                bar_rect = QRect(x, y, bar_width, bar_height)
                
                # Создаем градиент для полосы
                gradient = QLinearGradient(0, y + bar_height, 0, y)
                
                # Цвет зависит от высоты полосы
                color_index = min(i, len(self.bar_colors) - 1)
                base_color = self.bar_colors[color_index]
                
                # Затемняем цвет внизу, осветляем вверху
                dark_color = QColor(base_color)
                dark_color = dark_color.darker(150)
                
                bright_color = QColor(base_color)
                bright_color = bright_color.lighter(120)
                
                gradient.setColorAt(0, dark_color)
                gradient.setColorAt(1, bright_color)
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.NoPen)
                painter.drawRect(bar_rect)
            
            # Рисуем пик
            peak_height = int(widget_height * self.peak_values[i])
            if peak_height > bar_height + 2:  # Пик должен быть выше полосы
                peak_y = self.height() - 2 - peak_height
                peak_rect = QRect(x, peak_y, bar_width, 2)
                
                painter.setBrush(QBrush(self.peak_color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(peak_rect)
    
    def set_bars_count(self, count: int):
        """Изменить количество полос"""
        if count != self.bars_count:
            self.bars_count = count
            self.bar_values = [0.0] * count
            self.peak_values = [0.0] * count
            self.peak_decay = [0.0] * count
            self.bar_colors = self._create_gradient_colors()
            self.update()
    
    def set_demo_mode(self, enabled: bool):
        """Включить/выключить демонстрационный режим"""
        self.demo_mode = enabled
        if enabled:
            self.demo_timer.start(100)
        else:
            self.demo_timer.stop()
            # Сбрасываем значения
            self.bar_values = [0.0] * self.bars_count
            self.peak_values = [0.0] * self.bars_count
            self.peak_decay = [0.0] * self.bars_count
    
    def clear(self):
        """Очистить эквалайзер"""
        self.bar_values = [0.0] * self.bars_count
        self.peak_values = [0.0] * self.bars_count
        self.peak_decay = [0.0] * self.bars_count
        self.current_level = 0.0
        self.update()
    
    def set_colors(self, colors: List[QColor]):
        """Установить пользовательские цвета для полос"""
        if len(colors) == self.bars_count:
            self.bar_colors = colors
            self.update()
    
    def set_background_color(self, color: QColor):
        """Установить цвет фона"""
        self.background_color = color
        self.update()
    
    def set_peak_color(self, color: QColor):
        """Установить цвет пиков"""
        self.peak_color = color
        self.update()
    
    def get_status(self) -> dict:
        """Получить статус эквалайзера"""
        return {
            'bars_count': self.bars_count,
            'current_level': self.current_level,
            'demo_mode': self.demo_mode,
            'max_bar_value': max(self.bar_values) if self.bar_values else 0.0,
            'avg_bar_value': sum(self.bar_values) / len(self.bar_values) if self.bar_values else 0.0
        }