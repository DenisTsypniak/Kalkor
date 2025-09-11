"""
Backup Manager - Система резервного копіювання
"""
import os
import shutil
import zipfile
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

class BackupManager:
    """Менеджер резервного копіювання"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.max_backups = 10  # Максимальна кількість резервних копій
    
    def create_backup(self, source_paths: List[str], backup_name: Optional[str] = None) -> str:
        """Створення резервної копії"""
        try:
            if not backup_name:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = self.backup_dir / f"{backup_name}.zip"
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for source_path in source_paths:
                    if os.path.exists(source_path):
                        if os.path.isfile(source_path):
                            # Додаємо файл
                            zipf.write(source_path, os.path.basename(source_path))
                        elif os.path.isdir(source_path):
                            # Додаємо директорію
                            for root, dirs, files in os.walk(source_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, source_path)
                                    zipf.write(file_path, arcname)
            
            # Створюємо метадані
            metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "source_paths": source_paths,
                "backup_size": backup_path.stat().st_size,
                "version": "1.0"
            }
            
            metadata_path = self.backup_dir / f"{backup_name}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Backup created: {backup_path}")
            self._cleanup_old_backups()
            
            return str(backup_path)
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            raise
    
    def restore_backup(self, backup_path: str, restore_dir: str = ".") -> bool:
        """Відновлення з резервної копії"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            restore_path = Path(restore_dir)
            restore_path.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(restore_path)
            
            self.logger.info(f"Backup restored to: {restore_path}")
            return True
        except Exception as e:
            self.logger.error(f"Backup restoration failed: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Список доступних резервних копій"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.zip"):
            metadata_file = backup_file.with_suffix("_metadata.json")
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                except Exception as e:
                    self.logger.warning(f"Failed to read metadata for {backup_file}: {e}")
            else:
                # Створюємо базові метадані
                stat = backup_file.stat()
                backups.append({
                    "backup_name": backup_file.stem,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "backup_size": stat.st_size,
                    "version": "unknown"
                })
        
        # Сортуємо за датою створення
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups
    
    def delete_backup(self, backup_name: str) -> bool:
        """Видалення резервної копії"""
        try:
            backup_file = self.backup_dir / f"{backup_name}.zip"
            metadata_file = self.backup_dir / f"{backup_name}_metadata.json"
            
            if backup_file.exists():
                backup_file.unlink()
            
            if metadata_file.exists():
                metadata_file.unlink()
            
            self.logger.info(f"Backup deleted: {backup_name}")
            return True
        except Exception as e:
            self.logger.error(f"Backup deletion failed: {e}")
            return False
    
    def _cleanup_old_backups(self):
        """Очищення старих резервних копій"""
        try:
            backups = self.list_backups()
            
            if len(backups) > self.max_backups:
                # Видаляємо найстаріші резервні копії
                backups_to_delete = backups[self.max_backups:]
                
                for backup in backups_to_delete:
                    self.delete_backup(backup["backup_name"])
                
                self.logger.info(f"Cleaned up {len(backups_to_delete)} old backups")
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
    
    def create_database_backup(self, db_path: str, backup_name: Optional[str] = None) -> str:
        """Створення резервної копії бази даних"""
        try:
            if not backup_name:
                backup_name = f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = self.backup_dir / f"{backup_name}.db"
            
            # Копіюємо базу даних
            shutil.copy2(db_path, backup_path)
            
            # Створюємо метадані
            metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "source_db": db_path,
                "backup_size": backup_path.stat().st_size,
                "type": "database",
                "version": "1.0"
            }
            
            metadata_path = self.backup_dir / f"{backup_name}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Database backup created: {backup_path}")
            return str(backup_path)
        except Exception as e:
            self.logger.error(f"Database backup creation failed: {e}")
            raise
    
    def restore_database_backup(self, backup_path: str, target_db_path: str) -> bool:
        """Відновлення бази даних з резервної копії"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Створюємо резервну копію поточної БД
            current_backup = f"current_db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            if os.path.exists(target_db_path):
                shutil.copy2(target_db_path, self.backup_dir / current_backup)
            
            # Відновлюємо БД
            shutil.copy2(backup_file, target_db_path)
            
            self.logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Database restoration failed: {e}")
            return False
    
    def schedule_automatic_backup(self, source_paths: List[str], interval_hours: int = 24):
        """Планування автоматичного резервного копіювання"""
        try:
            schedule_file = self.backup_dir / "backup_schedule.json"
            
            schedule = {
                "enabled": True,
                "interval_hours": interval_hours,
                "source_paths": source_paths,
                "last_backup": None,
                "next_backup": (datetime.now() + timedelta(hours=interval_hours)).isoformat()
            }
            
            with open(schedule_file, 'w', encoding='utf-8') as f:
                json.dump(schedule, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Automatic backup scheduled every {interval_hours} hours")
        except Exception as e:
            self.logger.error(f"Backup scheduling failed: {e}")
    
    def check_automatic_backup(self) -> bool:
        """Перевірка чи потрібно створити автоматичну резервну копію"""
        try:
            schedule_file = self.backup_dir / "backup_schedule.json"
            
            if not schedule_file.exists():
                return False
            
            with open(schedule_file, 'r', encoding='utf-8') as f:
                schedule = json.load(f)
            
            if not schedule.get("enabled", False):
                return False
            
            next_backup = datetime.fromisoformat(schedule["next_backup"])
            
            if datetime.now() >= next_backup:
                # Створюємо резервну копію
                self.create_backup(schedule["source_paths"])
                
                # Оновлюємо розклад
                schedule["last_backup"] = datetime.now().isoformat()
                schedule["next_backup"] = (datetime.now() + timedelta(hours=schedule["interval_hours"])).isoformat()
                
                with open(schedule_file, 'w', encoding='utf-8') as f:
                    json.dump(schedule, f, indent=2, ensure_ascii=False)
                
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Automatic backup check failed: {e}")
            return False
    
    def get_backup_statistics(self) -> Dict[str, Any]:
        """Статистика резервних копій"""
        try:
            backups = self.list_backups()
            
            if not backups:
                return {"message": "No backups found"}
            
            total_size = sum(backup.get("backup_size", 0) for backup in backups)
            oldest_backup = min(backups, key=lambda x: x["created_at"])
            newest_backup = max(backups, key=lambda x: x["created_at"])
            
            return {
                "total_backups": len(backups),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_backup": oldest_backup["created_at"],
                "newest_backup": newest_backup["created_at"],
                "backup_dir": str(self.backup_dir),
                "max_backups": self.max_backups
            }
        except Exception as e:
            self.logger.error(f"Backup statistics failed: {e}")
            return {"error": str(e)}

# Глобальний екземпляр менеджера резервного копіювання
backup_manager = BackupManager()