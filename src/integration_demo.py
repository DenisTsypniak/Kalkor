"""
Демонстрація інтеграції нових систем з основним додатком
"""

import asyncio
import flet as ft
from src.core.integration import get_integrator

class IntegrationDemo:
    """Демонстрація роботи нових систем"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.integrator = get_integrator()
    
    async def show_integration_status(self):
        """Показує статус інтеграції систем"""
        
        # Створюємо контейнер для статусу
        status_container = ft.Container(
            content=ft.Column([
                ft.Text("🔧 Статус систем оптимізації", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                
                # Database Pool
                ft.Row([
                    ft.Icon(ft.Icons.DATABASE, color=ft.Colors.BLUE),
                    ft.Text("Connection Pooling: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('db_pool') else "❌ Неактивний", 
                           color=ft.Colors.GREEN if self.integrator.get_service('db_pool') else ft.Colors.RED)
                ]),
                
                # Animation Manager
                ft.Row([
                    ft.Icon(ft.Icons.ANIMATION, color=ft.Colors.PURPLE),
                    ft.Text("Animation Manager: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('animation_manager') else "❌ Неактивний",
                           color=ft.Colors.GREEN if self.integrator.get_service('animation_manager') else ft.Colors.RED)
                ]),
                
                # Theme Manager
                ft.Row([
                    ft.Icon(ft.Icons.PALETTE, color=ft.Colors.ORANGE),
                    ft.Text("Theme Manager: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('theme_manager') else "❌ Неактивний",
                           color=ft.Colors.GREEN if self.integrator.get_service('theme_manager') else ft.Colors.RED)
                ]),
                
                # Error Handler
                ft.Row([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED),
                    ft.Text("Error Handler: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('error_handler') else "❌ Неактивний",
                           color=ft.Colors.GREEN if self.integrator.get_service('error_handler') else ft.Colors.RED)
                ]),
                
                # Metrics Collector
                ft.Row([
                    ft.Icon(ft.Icons.ANALYTICS, color=ft.Colors.TEAL),
                    ft.Text("Metrics Collector: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('metrics_collector') else "❌ Неактивний",
                           color=ft.Colors.GREEN if self.integrator.get_service('metrics_collector') else ft.Colors.RED)
                ]),
                
                # Backup Manager
                ft.Row([
                    ft.Icon(ft.Icons.BACKUP, color=ft.Colors.INDIGO),
                    ft.Text("Backup Manager: ", size=16),
                    ft.Text("✅ Активний" if self.integrator.get_service('backup_manager') else "❌ Неактивний",
                           color=ft.Colors.GREEN if self.integrator.get_service('backup_manager') else ft.Colors.RED)
                ]),
                
                ft.Divider(),
                
                # Кнопки тестування
                ft.Row([
                    ft.ElevatedButton(
                        "🎨 Тест анімації",
                        on_click=self._test_animation,
                        bgcolor=ft.Colors.PURPLE_400
                    ),
                    ft.ElevatedButton(
                        "🎭 Змінити тему",
                        on_click=self._change_theme,
                        bgcolor=ft.Colors.ORANGE_400
                    ),
                    ft.ElevatedButton(
                        "📊 Показати метрики",
                        on_click=self._show_metrics,
                        bgcolor=ft.Colors.TEAL_400
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
                
            ]),
            padding=20,
            bgcolor=ft.Colors.GREY_900,
            border_radius=10,
            width=600
        )
        
        return status_container
    
    async def _test_animation(self, e):
        """Тестує анімації"""
        animation_manager = self.integrator.get_service('animation_manager')
        if animation_manager:
            # Створюємо тестовий контейнер
            test_container = ft.Container(
                width=100,
                height=100,
                bgcolor=ft.Colors.BLUE,
                border_radius=10
            )
            
            self.page.add(test_container)
            
            # Тестуємо різні анімації
            animation_manager.fade_in(test_container, duration=0.5)
            await asyncio.sleep(0.6)
            
            animation_manager.bounce(test_container, duration=0.6)
            await asyncio.sleep(0.7)
            
            animation_manager.fade_out(test_container, duration=0.3)
            await asyncio.sleep(0.4)
            
            self.page.controls.remove(test_container)
            self.page.update()
    
    async def _change_theme(self, e):
        """Змінює тему"""
        theme_manager = self.integrator.get_service('theme_manager')
        if theme_manager:
            current_theme = theme_manager.get_current_theme()
            if current_theme and current_theme.name == "Dark":
                theme_manager.set_theme("blue")
            else:
                theme_manager.set_theme("dark")
            
            # Оновлюємо UI
            self.page.bgcolor = theme_manager.get_color("background")
            self.page.update()
    
    async def _show_metrics(self, e):
        """Показує метрики"""
        metrics_collector = self.integrator.get_service('metrics_collector')
        if metrics_collector:
            report = metrics_collector.generate_report()
            
            # Створюємо діалог з метриками
            metrics_dialog = ft.AlertDialog(
                title=ft.Text("📊 Метрики продуктивності"),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"Операції: {len(report.get('operation_stats', {}))}"),
                        ft.Text(f"Системні метрики: {'✅' if report.get('system_summary') else '❌'}"),
                        ft.Text(f"UI метрики: {'✅' if report.get('ui_summary') else '❌'}"),
                        ft.Text(f"Метрики продуктивності: {'✅' if report.get('performance_summary') else '❌'}")
                    ], height=200),
                    width=400
                ),
                actions=[
                    ft.TextButton("Закрити", on_click=lambda e: self._close_dialog(metrics_dialog))
                ]
            )
            
            self.page.overlay.append(metrics_dialog)
            metrics_dialog.open = True
            self.page.update()
    
    def _close_dialog(self, dialog):
        """Закриває діалог"""
        dialog.open = False
        self.page.overlay.remove(dialog)
        self.page.update()

# Функція для додавання демо до основного додатку
async def add_integration_demo_to_app(app_instance):
    """Додає демо інтеграції до основного додатку"""
    
    # Створюємо демо
    demo = IntegrationDemo(app_instance.page)
    
    # Додаємо кнопку демо до UI
    demo_button = ft.ElevatedButton(
        "🔧 Системи оптимізації",
        on_click=lambda e: _show_integration_demo(demo),
        bgcolor=ft.Colors.INDIGO_400,
        icon=ft.Icons.SETTINGS
    )
    
    return demo_button

async def _show_integration_demo(demo):
    """Показує демо інтеграції"""
    status_container = await demo.show_integration_status()
    
    # Створюємо діалог
    demo_dialog = ft.AlertDialog(
        title=ft.Text("🔧 Системи оптимізації"),
        content=status_container,
        actions=[
            ft.TextButton("Закрити", on_click=lambda e: demo._close_dialog(demo_dialog))
        ]
    )
    
    demo.page.overlay.append(demo_dialog)
    demo_dialog.open = True
    demo.page.update()
