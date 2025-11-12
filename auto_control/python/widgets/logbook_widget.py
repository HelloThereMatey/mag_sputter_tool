"""
Logbook Widget for Sputter Control System

Simple logbook table to track target materials and users.

Database Location: {project_root}/logbook.db (SQLite format)
CSV Export: {project_root}/logbook.csv (automatically updated)
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QLineEdit, QLabel,
                             QHeaderView, QMessageBox)
from PyQt5.QtCore import Qt
from datetime import datetime
import sqlite3
import csv
from pathlib import Path


class LogbookWidget(QWidget):
    """Widget for displaying and managing the sputter system logbook."""
    
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        
        # Set window flags to make this an independent window
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        
        self.db_path = Path(__file__).parent.parent.parent / "logbook.db"
        self.csv_path = Path(__file__).parent.parent.parent / "logbook.csv"
        self.parent_window = parent  # Store reference to parent window
        self.current_user = current_user  # Store current user info
        self._init_database()
        self._init_ui()
        self._load_entries()
        self._load_last_targets()  # Pre-fill gun targets from last entry
    
    def _init_database(self):
        """Initialize SQLite database and create table if needed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                gun1_target TEXT NOT NULL,
                gun2_target TEXT NOT NULL,
                user_name TEXT NOT NULL,
                notes TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Input fields
        input_layout = QHBoxLayout()
        
        self.gun1_input = QLineEdit()
        self.gun1_input.setPlaceholderText("Gun 1 Target Material")
        
        self.gun2_input = QLineEdit()
        self.gun2_input.setPlaceholderText("Gun 2 Target Material")
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("User Name")
        # Auto-fill username from current user and make read-only
        if self.current_user:
            username = self.current_user.get('username', 'Unknown')
            self.user_input.setText(username)
            self.user_input.setReadOnly(True)
            self.user_input.setStyleSheet("QLineEdit { background-color: #f0f0f0; }")
        
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes (optional)")
        
        add_button = QPushButton("Add Entry")
        add_button.clicked.connect(self._add_entry)
        
        input_layout.addWidget(QLabel("User Name:"))
        input_layout.addWidget(self.user_input)
        input_layout.addWidget(QLabel("Gun 1:"))
        input_layout.addWidget(self.gun1_input)
        input_layout.addWidget(QLabel("Gun 2:"))
        input_layout.addWidget(self.gun2_input)
        input_layout.addWidget(QLabel("Notes:"))
        input_layout.addWidget(self.notes_input)
        input_layout.addWidget(add_button)
        
        layout.addLayout(input_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date", "User Name", "Gun 1 Target", "Gun 2 Target", "Notes"])
        
        # Set column widths - Notes column takes half the width, others split the remaining half
        header = self.table.horizontalHeader()
        
        # Calculate proportional widths
        # Total table width will be 1400 (from resize below)
        # Notes gets 50%, other 4 columns split the remaining 50% (12.5% each)
        total_width = 1400
        notes_width = total_width // 2  # 50% for Notes
        other_width = (total_width - notes_width) // 4  # Split remaining 50% among 4 columns
        
        # Set fixed widths for all columns
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, other_width)  # Date
        self.table.setColumnWidth(1, other_width)  # User Name
        self.table.setColumnWidth(2, other_width)  # Gun 1
        self.table.setColumnWidth(3, other_width)  # Gun 2
        self.table.setColumnWidth(4, notes_width)  # Notes - 50% of table width
        
        # Make only Notes column editable
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemChanged.connect(self._on_item_changed)
        
        layout.addWidget(self.table)
        
        # Delete button
        delete_button = QPushButton("Delete Selected Entry")
        delete_button.clicked.connect(self._delete_entry)
        layout.addWidget(delete_button)
        
        self.setWindowTitle("Sputter System Logbook")
        self.resize(1400, 600)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Accept the close event
        event.accept()
        # Ensure the window is properly destroyed
        self.deleteLater()
    
    def _load_last_targets(self):
        """Pre-fill gun target fields with last entry values."""
        gun1, gun2 = self.get_latest_targets()
        if gun1:
            self.gun1_input.setText(gun1)
        if gun2:
            self.gun2_input.setText(gun2)
    
    def _on_item_changed(self, item):
        """Handle cell edit - only allow editing Notes column."""
        if item.column() != 4:  # Not the Notes column
            return
        
        # Get the date from this row (column 0)
        date_item = self.table.item(item.row(), 0)
        if not date_item:
            return
        
        date = date_item.text()
        new_notes = item.text()
        
        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE logbook SET notes = ? WHERE date = ?", (new_notes, date))
        conn.commit()
        conn.close()
        
        # Update CSV
        self._export_to_csv()
        
        print(f"📝 Updated notes for entry {date}")
    
    def _export_to_csv(self):
        """Export logbook database to CSV file."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT date, user_name, gun1_target, gun2_target, notes FROM logbook ORDER BY date DESC")
            entries = cursor.fetchall()
            conn.close()
            
            # Write to CSV
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Date", "User Name", "Gun 1 Target", "Gun 2 Target", "Notes"])
                writer.writerows(entries)
            
            print(f"📄 Exported {len(entries)} entries to {self.csv_path}")
            
        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
    
    def _add_entry(self):
        """Add a new logbook entry."""
        gun1 = self.gun1_input.text().strip()
        gun2 = self.gun2_input.text().strip()
        user = self.user_input.text().strip()
        notes = self.notes_input.text().strip()
        
        if not gun1 or not gun2 or not user:
            QMessageBox.warning(self, "Input Error", "Please fill in Gun 1, Gun 2, and User fields")
            return
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logbook (date, gun1_target, gun2_target, user_name, notes) VALUES (?, ?, ?, ?, ?)",
            (date, gun1, gun2, user, notes)
        )
        conn.commit()
        conn.close()
        
        # Clear inputs (except user which is auto-filled)
        self.gun1_input.clear()
        self.gun2_input.clear()
        self.notes_input.clear()
        
        # Reload table
        self._load_entries()
        
        # Update parent window labels if available
        self._update_parent_labels()
        
        # Export to CSV
        self._export_to_csv()
        
        # Pre-fill gun targets for next entry
        self._load_last_targets()
    
    def _delete_entry(self):
        """Delete selected logbook entry."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an entry to delete")
            return
        
        # Get the date from the selected row (used as identifier)
        date_item = self.table.item(current_row, 0)
        if not date_item:
            return
        
        date = date_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete entry from {date}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM logbook WHERE date = ?", (date,))
            conn.commit()
            conn.close()
            
            self._load_entries()
            
            # Update parent window labels if available
            self._update_parent_labels()
            
            # Export to CSV
            self._export_to_csv()
    
    def _load_entries(self):
        """Load all logbook entries from database."""
        # Block signals while loading to prevent triggering itemChanged
        self.table.blockSignals(True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT date, user_name, gun1_target, gun2_target, notes FROM logbook ORDER BY date DESC")
        entries = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(len(entries))
        
        for row, (date, user, gun1, gun2, notes) in enumerate(entries):
            # Create non-editable items for all columns except Notes
            # Column order: Date, User Name, Gun 1 Target, Gun 2 Target, Notes
            date_item = QTableWidgetItem(date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, date_item)
            
            user_item = QTableWidgetItem(user)
            user_item.setFlags(user_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, user_item)
            
            gun1_item = QTableWidgetItem(gun1)
            gun1_item.setFlags(gun1_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, gun1_item)
            
            gun2_item = QTableWidgetItem(gun2)
            gun2_item.setFlags(gun2_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, gun2_item)
            
            # Notes column is editable
            notes_item = QTableWidgetItem(notes if notes else "")
            self.table.setItem(row, 4, notes_item)
        
        # Re-enable signals
        self.table.blockSignals(False)
    
    def get_latest_targets(self):
        """Get the most recent gun target entries from the database.
        
        Returns:
            tuple: (gun1_target, gun2_target) or (None, None) if no entries exist
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT gun1_target, gun2_target FROM logbook ORDER BY date DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0], result[1]
        return None, None
    
    def _update_parent_labels(self):
        """Update the Gun1Target and Gun2Target labels in the parent window."""
        if self.parent_window is None:
            return
        
        gun1, gun2 = self.get_latest_targets()
        
        # Update Gun1Target label
        if hasattr(self.parent_window, 'Gun1Target'):
            if gun1:
                self.parent_window.Gun1Target.setText(f"Gun #1: {gun1}")
            else:
                self.parent_window.Gun1Target.setText("Gun #1: ")
        
        # Update Gun2Target label
        if hasattr(self.parent_window, 'Gun2Target'):
            if gun2:
                self.parent_window.Gun2Target.setText(f"Gun #2: {gun2}")
            else:
                self.parent_window.Gun2Target.setText("Gun #2: ")
