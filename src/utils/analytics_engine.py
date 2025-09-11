"""
Analytics Engine - Система аналітики та звітів
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

@dataclass
class AnalyticsData:
    """Структура даних аналітики"""
    period: str
    total_income: float
    total_expenses: float
    net_profit: float
    transaction_count: int
    average_transaction: float
    top_categories: List[Dict[str, Any]]
    trends: Dict[str, Any]

class AnalyticsEngine:
    """Движок аналітики"""
    
    def __init__(self, db_path: str = "tracker.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def get_financial_summary(self, profile_id: int, period_days: int = 30) -> AnalyticsData:
        """Отримання фінансового підсумку"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Загальні доходи та витрати
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
                        SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
                        COUNT(*) as transaction_count
                    FROM transactions 
                    WHERE profile_id = ? AND date BETWEEN ? AND ?
                """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                result = cursor.fetchone()
                total_income = result['total_income'] or 0
                total_expenses = result['total_expenses'] or 0
                transaction_count = result['transaction_count'] or 0
                
                # Топ категорії
                top_categories = self._get_top_categories(cursor, profile_id, start_date, end_date)
                
                # Тренди
                trends = self._calculate_trends(cursor, profile_id, start_date, end_date)
                
                return AnalyticsData(
                    period=f"{period_days} days",
                    total_income=total_income,
                    total_expenses=total_expenses,
                    net_profit=total_income - total_expenses,
                    transaction_count=transaction_count,
                    average_transaction=(total_income + total_expenses) / transaction_count if transaction_count > 0 else 0,
                    top_categories=top_categories,
                    trends=trends
                )
        except Exception as e:
            self.logger.error(f"Financial summary failed: {e}")
            raise
    
    def _get_top_categories(self, cursor: sqlite3.Cursor, profile_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Отримання топ категорій"""
        try:
            cursor.execute("""
                SELECT 
                    category,
                    type,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count
                FROM transactions 
                WHERE profile_id = ? AND date BETWEEN ? AND ?
                GROUP BY category, type
                ORDER BY total_amount DESC
                LIMIT 10
            """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            categories = []
            for row in cursor.fetchall():
                categories.append({
                    "category": row['category'],
                    "type": row['type'],
                    "total_amount": row['total_amount'],
                    "transaction_count": row['transaction_count']
                })
            
            return categories
        except Exception as e:
            self.logger.error(f"Top categories failed: {e}")
            return []
    
    def _calculate_trends(self, cursor: sqlite3.Cursor, profile_id: int, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Розрахунок трендів"""
        try:
            # Розділяємо період на дві половини
            mid_date = start_date + (end_date - start_date) / 2
            
            # Перша половина
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
                FROM transactions 
                WHERE profile_id = ? AND date BETWEEN ? AND ?
            """, (profile_id, start_date.strftime('%Y-%m-%d'), mid_date.strftime('%Y-%m-%d')))
            
            first_half = cursor.fetchone()
            
            # Друга половина
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
                FROM transactions 
                WHERE profile_id = ? AND date BETWEEN ? AND ?
            """, (profile_id, mid_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            second_half = cursor.fetchone()
            
            # Розраховуємо зміни
            income_change = self._calculate_percentage_change(
                first_half['income'] or 0, 
                second_half['income'] or 0
            )
            
            expense_change = self._calculate_percentage_change(
                first_half['expenses'] or 0, 
                second_half['expenses'] or 0
            )
            
            return {
                "income_trend": income_change,
                "expense_trend": expense_change,
                "profit_trend": income_change - expense_change
            }
        except Exception as e:
            self.logger.error(f"Trends calculation failed: {e}")
            return {}
    
    def _calculate_percentage_change(self, old_value: float, new_value: float) -> float:
        """Розрахунок відсоткової зміни"""
        if old_value == 0:
            return 100.0 if new_value > 0 else 0.0
        
        return ((new_value - old_value) / old_value) * 100
    
    def get_monthly_report(self, profile_id: int, year: int, month: int) -> Dict[str, Any]:
        """Місячний звіт"""
        try:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Денна статистика
                cursor.execute("""
                    SELECT 
                        DATE(date) as day,
                        SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as daily_income,
                        SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as daily_expenses,
                        COUNT(*) as daily_transactions
                    FROM transactions 
                    WHERE profile_id = ? AND date BETWEEN ? AND ?
                    GROUP BY DATE(date)
                    ORDER BY day
                """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                daily_data = []
                for row in cursor.fetchall():
                    daily_data.append({
                        "day": row['day'],
                        "income": row['daily_income'] or 0,
                        "expenses": row['daily_expenses'] or 0,
                        "transactions": row['daily_transactions'] or 0
                    })
                
                # Загальна статистика
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
                        SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
                        COUNT(*) as total_transactions
                    FROM transactions 
                    WHERE profile_id = ? AND date BETWEEN ? AND ?
                """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                total = cursor.fetchone()
                
                return {
                    "period": f"{year}-{month:02d}",
                    "total_income": total['total_income'] or 0,
                    "total_expenses": total['total_expenses'] or 0,
                    "net_profit": (total['total_income'] or 0) - (total['total_expenses'] or 0),
                    "total_transactions": total['total_transactions'] or 0,
                    "daily_data": daily_data,
                    "average_daily_income": (total['total_income'] or 0) / len(daily_data) if daily_data else 0,
                    "average_daily_expenses": (total['total_expenses'] or 0) / len(daily_data) if daily_data else 0
                }
        except Exception as e:
            self.logger.error(f"Monthly report failed: {e}")
            raise
    
    def get_category_analysis(self, profile_id: int, period_days: int = 30) -> Dict[str, Any]:
        """Аналіз по категоріях"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Аналіз доходів по категоріях
                cursor.execute("""
                    SELECT 
                        category,
                        SUM(amount) as total_amount,
                        COUNT(*) as transaction_count,
                        AVG(amount) as average_amount
                    FROM transactions 
                    WHERE profile_id = ? AND type = 'income' AND date BETWEEN ? AND ?
                    GROUP BY category
                    ORDER BY total_amount DESC
                """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                income_categories = []
                for row in cursor.fetchall():
                    income_categories.append({
                        "category": row['category'],
                        "total_amount": row['total_amount'],
                        "transaction_count": row['transaction_count'],
                        "average_amount": row['average_amount']
                    })
                
                # Аналіз витрат по категоріях
                cursor.execute("""
                    SELECT 
                        category,
                        SUM(amount) as total_amount,
                        COUNT(*) as transaction_count,
                        AVG(amount) as average_amount
                    FROM transactions 
                    WHERE profile_id = ? AND type = 'expense' AND date BETWEEN ? AND ?
                    GROUP BY category
                    ORDER BY total_amount DESC
                """, (profile_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                expense_categories = []
                for row in cursor.fetchall():
                    expense_categories.append({
                        "category": row['category'],
                        "total_amount": row['total_amount'],
                        "transaction_count": row['transaction_count'],
                        "average_amount": row['average_amount']
                    })
                
                return {
                    "period_days": period_days,
                    "income_categories": income_categories,
                    "expense_categories": expense_categories,
                    "total_income_categories": len(income_categories),
                    "total_expense_categories": len(expense_categories)
                }
        except Exception as e:
            self.logger.error(f"Category analysis failed: {e}")
            raise
    
    def get_property_analytics(self, profile_id: int) -> Dict[str, Any]:
        """Аналітика майна"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Загальна статистика майна
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_properties,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_properties,
                        SUM(CASE WHEN status = 'sold' THEN 1 ELSE 0 END) as sold_properties,
                        SUM(CASE WHEN status = 'active' THEN purchase_price ELSE 0 END) as total_investment,
                        SUM(CASE WHEN status = 'sold' THEN sale_price ELSE 0 END) as total_sales
                    FROM properties 
                    WHERE profile_id = ?
                """, (profile_id,))
                
                stats = cursor.fetchone()
                
                # Топ майно за прибутком
                cursor.execute("""
                    SELECT 
                        name,
                        purchase_price,
                        sale_price,
                        (sale_price - purchase_price) as profit,
                        status
                    FROM properties 
                    WHERE profile_id = ? AND status = 'sold'
                    ORDER BY profit DESC
                    LIMIT 5
                """, (profile_id,))
                
                top_properties = []
                for row in cursor.fetchall():
                    top_properties.append({
                        "name": row['name'],
                        "purchase_price": row['purchase_price'],
                        "sale_price": row['sale_price'],
                        "profit": row['profit'],
                        "status": row['status']
                    })
                
                return {
                    "total_properties": stats['total_properties'] or 0,
                    "active_properties": stats['active_properties'] or 0,
                    "sold_properties": stats['sold_properties'] or 0,
                    "total_investment": stats['total_investment'] or 0,
                    "total_sales": stats['total_sales'] or 0,
                    "total_profit": (stats['total_sales'] or 0) - (stats['total_investment'] or 0),
                    "top_properties": top_properties
                }
        except Exception as e:
            self.logger.error(f"Property analytics failed: {e}")
            raise
    
    def export_analytics_report(self, profile_id: int, report_type: str = "summary") -> str:
        """Експорт звіту аналітики"""
        try:
            if report_type == "summary":
                data = self.get_financial_summary(profile_id)
            elif report_type == "monthly":
                now = datetime.now()
                data = self.get_monthly_report(profile_id, now.year, now.month)
            elif report_type == "category":
                data = self.get_category_analysis(profile_id)
            elif report_type == "property":
                data = self.get_property_analytics(profile_id)
            else:
                raise ValueError(f"Unknown report type: {report_type}")
            
            # Конвертуємо в JSON
            if hasattr(data, '__dict__'):
                report_data = data.__dict__
            else:
                report_data = data
            
            report_json = json.dumps(report_data, indent=2, ensure_ascii=False, default=str)
            
            # Зберігаємо в файл
            report_file = f"analytics_report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_json)
            
            self.logger.info(f"Analytics report exported: {report_file}")
            return report_file
        except Exception as e:
            self.logger.error(f"Analytics export failed: {e}")
            raise

# Глобальний екземпляр движка аналітики
analytics_engine = AnalyticsEngine()
