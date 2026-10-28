"""
QuickFill configuration GUI.

Overview table (read-only): Deck | Note Type | Display Name
Row editor dialog: identity + fetcher + mapping + mask + CSV path

Persists via mw.addonManager.writeConfig. Mapping / source_field / mask_fields
are stored as field *indices* to match the existing fetch path.
"""

from __future__ import annotations

from typing import Any, Optional

from aqt import mw
from aqt.qt import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    Qt,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
    pyqtSignal,
)

from . import fetchers


def _as_independent_window(widget: QWidget) -> None:
    """
    Top-level window with min/max/close so it can move and resize freely.

    A plain QDialog parented to mw is often grouped with the main window by
    the window manager; moving one then moves the other. Qt.Window breaks that
    link while keeping normal dialog chrome.
    """
    widget.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    # Non-modal: can interact with Anki while the config is open, and the
    # dialog is not tied to the main window's stacking group the same way.
    widget.setWindowModality(Qt.WindowModality.NonModal)


# Suggested mapping keys when a fetcher does not declare its own list.
_DEFAULT_OUTPUT_KEYS: dict[str, list[str]] = {
    "cambridge_en_tc": ["word", "pronunciation", "pos", "inflections", "def_zh", "examples"],
    "cambridge_en_ja": ["word", "pronunciation", "pos", "inflections", "def_ja", "examples"],
    "yahoo_en_tc": ["word", "pronunciation", "pos", "inflections", "def_zh", "examples"],
    "local_csv": ["word", "phonetic", "pos", "translation", "exchanges", "frq"],
    "mw": ["word", "definition", "example", "pronunciation", "pos"],
    "mw_kids": ["word", "definition", "example"],
    "oxford": [
        "word",
        "pos",
        "pronunciation",
        "inflections",
        "definition",
        "examples",
        "etymology",
        "cefr",
    ],
}

_CSV_FETCHERS = {"local_csv"}
_ANY_DECK = "(any deck)"


def _addon_dir() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _load_raw_config() -> dict:
    return dict(mw.addonManager.getConfig(_addon_dir()) or {})


def _save_raw_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(_addon_dir(), cfg)


def _fetcher_names() -> list[str]:
    names: list[str] = []
    for cls in getattr(fetchers, "all_fetchers", []) or []:
        try:
            n = cls.source_name()
            if n and isinstance(n, str):
                names.append(n)
        except Exception:
            continue
    # Stable order; include known keys even if a fetcher failed to import
    for extra in _DEFAULT_OUTPUT_KEYS:
        if extra not in names:
            names.append(extra)
    return sorted(set(names))


def _output_keys_for(fetcher: str) -> list[str]:
    return list(_DEFAULT_OUTPUT_KEYS.get(fetcher, []))


def _note_type_names() -> list[str]:
    if not mw.col:
        return []
    try:
        return sorted(mw.col.models.all_names())
    except Exception:
        return sorted(m["name"] for m in mw.col.models.all())


def _fields_for_note_type(name: str) -> list[str]:
    if not mw.col or not name:
        return []
    model = mw.col.models.by_name(name)
    if not model:
        return []
    return [f["name"] for f in model["flds"]]


def _deck_names() -> list[str]:
    names = [_ANY_DECK]
    if not mw.col:
        return names
    try:
        names.extend(sorted(mw.col.decks.all_names()))
    except Exception:
        try:
            names.extend(sorted(d["name"] for d in mw.col.decks.all()))
        except Exception:
            pass
    # de-dupe preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _index_to_name(fields: list[str], idx: Any) -> str:
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return ""
    if 0 <= i < len(fields):
        return fields[i]
    return ""


def _name_to_index(fields: list[str], name: str) -> int:
    try:
        return fields.index(name)
    except ValueError:
        return -1


def sources_from_config(cfg: dict) -> list[dict]:
    """Flatten models → list of source dicts with note_type / deck attached."""
    rows: list[dict] = []
    models = cfg.get("models") or {}
    for note_type, sources in models.items():
        if not isinstance(sources, list):
            continue
        for src in sources:
            if not isinstance(src, dict):
                continue
            row = dict(src)
            row["note_type"] = note_type
            row.setdefault("deck", _ANY_DECK)
            row.setdefault("name", row.get("fetcher", "Unnamed"))
            rows.append(row)
    return rows


def sources_to_config(rows: list[dict], base: Optional[dict] = None) -> dict:
    """Rebuild config.json shape from flat source rows."""
    cfg = dict(base or {})
    models: dict[str, list] = {}
    for row in rows:
        note_type = row.get("note_type") or "Basic"
        entry = {
            "name": row.get("name") or row.get("fetcher") or "Unnamed",
            "fetcher": row.get("fetcher") or "local_csv",
            "source_field": int(row.get("source_field", 0)),
            "mapping": dict(row.get("mapping") or {}),
            "config": dict(row.get("config") or {}),
        }
        deck = row.get("deck") or _ANY_DECK
        if deck and deck != _ANY_DECK:
            entry["deck"] = deck
        if row.get("mask_fields"):
            entry["mask_fields"] = list(row["mask_fields"])
        if row.get("mask_mode"):
            entry["mask_mode"] = row["mask_mode"]
        if row.get("mask_class"):
            entry["mask_class"] = row["mask_class"]
        if row.get("mask_tag"):
            entry["mask_tag"] = row["mask_tag"]
        if row.get("mask_placeholder"):
            entry["mask_placeholder"] = row["mask_placeholder"]
        models.setdefault(note_type, []).append(entry)
    cfg["models"] = models
    return cfg


# ---------------------------------------------------------------------------
# Checkable multi-select for mask fields
# ---------------------------------------------------------------------------

class CheckableListDropdown(QToolButton):
    selection_changed = pyqtSignal(list)

    def __init__(self, items: list[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumWidth(200)
        self._items = list(items)
        self._checks: dict[str, QCheckBox] = {}
        self._rebuild_menu()
        self._update_label()

    def _rebuild_menu(self) -> None:
        from aqt.qt import QMenu

        menu = self.menu() or QMenu(self)
        menu.clear()
        self._checks.clear()
        for name in self._items:
            cb = QCheckBox(name)
            cb.stateChanged.connect(self._on_toggle)
            self._checks[name] = cb
            action = QWidgetAction(menu)
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(8, 4, 8, 4)
            lay.addWidget(cb)
            action.setDefaultWidget(wrap)
            menu.addAction(action)
        menu.addSeparator()
        clear_act = QAction("Clear all", menu)
        clear_act.triggered.connect(self.clear)
        menu.addAction(clear_act)
        self.setMenu(menu)

    def set_items(self, items: list[str]) -> None:
        selected = set(self.selected())
        self._items = list(items)
        self._rebuild_menu()
        self.set_selected([x for x in self._items if x in selected])

    def selected(self) -> list[str]:
        return [n for n, cb in self._checks.items() if cb.isChecked()]

    def set_selected(self, names: list[str]) -> None:
        wanted = set(names)
        for name, cb in self._checks.items():
            cb.blockSignals(True)
            cb.setChecked(name in wanted)
            cb.blockSignals(False)
        self._update_label()

    def clear(self) -> None:
        for cb in self._checks.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._update_label()
        self.selection_changed.emit([])

    def _on_toggle(self, _state: int = 0) -> None:
        self._update_label()
        self.selection_changed.emit(self.selected())

    def _update_label(self) -> None:
        sel = self.selected()
        if not sel:
            self.setText("Select fields…")
        elif len(sel) <= 2:
            self.setText(", ".join(sel))
        else:
            self.setText(f"{len(sel)} fields selected")


# ---------------------------------------------------------------------------
# Row editor
# ---------------------------------------------------------------------------

class RowConfigWidget(QWidget):
    """Edit one source: identity + fetcher + mapping + mask (+ CSV)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._note_fields: list[str] = []

        root = QVBoxLayout(self)

        ident = QGroupBox("Identity")
        ident_form = QFormLayout(ident)
        self.deck_combo = QComboBox()
        self.deck_combo.addItems(_deck_names())
        ident_form.addRow("Deck", self.deck_combo)

        self.note_type_combo = QComboBox()
        self.note_type_combo.addItems(_note_type_names() or ["Basic"])
        self.note_type_combo.currentTextChanged.connect(self._on_note_type_changed)
        ident_form.addRow("Note type", self.note_type_combo)

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("Friendly name shown in menus")
        ident_form.addRow("Display name", self.display_name_edit)
        root.addWidget(ident)

        core = QGroupBox("Source")
        core_form = QFormLayout(core)
        self.fetcher_combo = QComboBox()
        self.fetcher_combo.addItems(_fetcher_names())
        self.fetcher_combo.currentTextChanged.connect(self._on_fetcher_changed)
        core_form.addRow("Fetcher", self.fetcher_combo)

        self.source_field_combo = QComboBox()
        core_form.addRow("Source field", self.source_field_combo)
        root.addWidget(core)

        self.csv_group = QGroupBox("CSV options")
        csv_lay = QHBoxLayout(self.csv_group)
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("/path/to/dictionary.csv")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_csv)
        csv_lay.addWidget(self.csv_path_edit)
        csv_lay.addWidget(browse)
        root.addWidget(self.csv_group)

        map_box = QGroupBox("Field mapping (fetcher output → note field)")
        map_lay = QVBoxLayout(map_box)
        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["Output key", "Note field"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setMinimumHeight(150)
        map_lay.addWidget(self.mapping_table)
        map_btns = QHBoxLayout()
        add_map = QPushButton("Add row")
        add_map.clicked.connect(lambda: self._add_mapping_row())
        rm_map = QPushButton("Remove selected")
        rm_map.clicked.connect(self._remove_mapping_row)
        fill_btn = QPushButton("Fill from fetcher keys")
        fill_btn.clicked.connect(self._fill_fetcher_keys)
        map_btns.addWidget(add_map)
        map_btns.addWidget(rm_map)
        map_btns.addStretch()
        map_btns.addWidget(fill_btn)
        map_lay.addLayout(map_btns)
        root.addWidget(map_box)

        mask_box = QGroupBox("Stem mask")
        mask_form = QFormLayout(mask_box)
        self.mask_fields_dd = CheckableListDropdown([])
        mask_form.addRow("Mask fields", self.mask_fields_dd)
        self.mask_mode_combo = QComboBox()
        self.mask_mode_combo.addItems(["tag", "replace"])
        self.mask_mode_combo.currentTextChanged.connect(self._on_mask_mode_changed)
        mask_form.addRow("Mask mode", self.mask_mode_combo)
        self.mask_class_edit = QLineEdit("qf-headword")
        mask_form.addRow("Mask CSS class", self.mask_class_edit)
        self.mask_tag_edit = QLineEdit("span")
        mask_form.addRow("Mask HTML tag", self.mask_tag_edit)
        self.mask_placeholder_edit = QLineEdit("#$#")
        mask_form.addRow("Mask placeholder", self.mask_placeholder_edit)
        root.addWidget(mask_box)

        # Seed field lists for current note type
        self._apply_note_type(self.note_type_combo.currentText())
        self._on_fetcher_changed(self.fetcher_combo.currentText())
        self._on_mask_mode_changed(self.mask_mode_combo.currentText())

    def load_source(self, src: dict) -> None:
        fields = _fields_for_note_type(src.get("note_type") or "")

        deck = src.get("deck") or _ANY_DECK
        idx = self.deck_combo.findText(deck)
        if idx < 0:
            self.deck_combo.addItem(deck)
            idx = self.deck_combo.findText(deck)
        self.deck_combo.setCurrentIndex(max(idx, 0))

        note_type = src.get("note_type") or (
            self.note_type_combo.currentText() or "Basic"
        )
        self.note_type_combo.blockSignals(True)
        idx = self.note_type_combo.findText(note_type)
        if idx < 0:
            self.note_type_combo.addItem(note_type)
            idx = self.note_type_combo.findText(note_type)
        self.note_type_combo.setCurrentIndex(max(idx, 0))
        self.note_type_combo.blockSignals(False)
        self._apply_note_type(self.note_type_combo.currentText())
        fields = self._note_fields

        self.display_name_edit.setText(src.get("name") or "")

        fetcher = src.get("fetcher") or "local_csv"
        idx = self.fetcher_combo.findText(fetcher)
        if idx < 0:
            self.fetcher_combo.addItem(fetcher)
            idx = self.fetcher_combo.findText(fetcher)
        self.fetcher_combo.setCurrentIndex(max(idx, 0))

        src_field_name = _index_to_name(fields, src.get("source_field", 0))
        idx = self.source_field_combo.findText(src_field_name)
        self.source_field_combo.setCurrentIndex(idx if idx >= 0 else 0)

        conf = src.get("config") or {}
        self.csv_path_edit.setText(conf.get("csv_path") or "")

        self.mapping_table.setRowCount(0)
        mapping = src.get("mapping") or {}
        for key, field_idx in mapping.items():
            dest = _index_to_name(fields, field_idx)
            self._add_mapping_row(str(key), dest)

        mask_names = [
            _index_to_name(fields, i)
            for i in (src.get("mask_fields") or [])
            if _index_to_name(fields, i)
        ]
        self.mask_fields_dd.set_selected(mask_names)

        mode = src.get("mask_mode") or "tag"
        idx = self.mask_mode_combo.findText(mode)
        self.mask_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mask_class_edit.setText(src.get("mask_class") or "qf-headword")
        self.mask_tag_edit.setText(src.get("mask_tag") or "span")
        self.mask_placeholder_edit.setText(src.get("mask_placeholder") or "#$#")

        self._on_fetcher_changed(self.fetcher_combo.currentText())
        self._on_mask_mode_changed(self.mask_mode_combo.currentText())

    def result_source(self) -> dict:
        fields = self._note_fields
        mapping: dict[str, int] = {}
        for row in range(self.mapping_table.rowCount()):
            key_w = self.mapping_table.cellWidget(row, 0)
            field_w = self.mapping_table.cellWidget(row, 1)
            if not isinstance(key_w, QComboBox) or not isinstance(field_w, QComboBox):
                continue
            key = key_w.currentText().strip()
            dest = field_w.currentText()
            if not key or dest == "(skip)" or not dest:
                continue
            idx = _name_to_index(fields, dest)
            if idx >= 0:
                mapping[key] = idx

        mask_fields = [
            _name_to_index(fields, n)
            for n in self.mask_fields_dd.selected()
            if _name_to_index(fields, n) >= 0
        ]

        src_idx = _name_to_index(fields, self.source_field_combo.currentText())
        if src_idx < 0:
            src_idx = 0

        config: dict[str, Any] = {}
        fetcher = self.fetcher_combo.currentText()
        if fetcher in _CSV_FETCHERS:
            path = self.csv_path_edit.text().strip()
            if path:
                config["csv_path"] = path
            config.setdefault("csv_search_field", "word")
            config.setdefault("csv_sorted", True)
            config.setdefault("delimiter", ",")

        out: dict[str, Any] = {
            "deck": self.deck_combo.currentText() or _ANY_DECK,
            "note_type": self.note_type_combo.currentText() or "Basic",
            "name": self.display_name_edit.text().strip()
            or self.fetcher_combo.currentText()
            or "Unnamed",
            "fetcher": fetcher,
            "source_field": src_idx,
            "mapping": mapping,
            "config": config,
            "mask_fields": mask_fields,
            "mask_mode": self.mask_mode_combo.currentText(),
            "mask_class": self.mask_class_edit.text().strip() or "qf-headword",
            "mask_tag": self.mask_tag_edit.text().strip() or "span",
            "mask_placeholder": self.mask_placeholder_edit.text().strip() or "#$#",
        }
        return out

    def _on_note_type_changed(self, note_type: str) -> None:
        self._apply_note_type(note_type)

    def _apply_note_type(self, note_type: str) -> None:
        fields = _fields_for_note_type(note_type) or ["Front", "Back"]
        self._note_fields = fields

        cur = self.source_field_combo.currentText()
        self.source_field_combo.blockSignals(True)
        self.source_field_combo.clear()
        self.source_field_combo.addItems(fields)
        idx = self.source_field_combo.findText(cur)
        self.source_field_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.source_field_combo.blockSignals(False)

        self.mask_fields_dd.set_items(fields)

        for row in range(self.mapping_table.rowCount()):
            field_w = self.mapping_table.cellWidget(row, 1)
            if isinstance(field_w, QComboBox):
                prev = field_w.currentText()
                field_w.blockSignals(True)
                field_w.clear()
                field_w.addItem("(skip)")
                field_w.addItems(fields)
                idx = field_w.findText(prev)
                field_w.setCurrentIndex(idx if idx >= 0 else 0)
                field_w.blockSignals(False)

    def _on_fetcher_changed(self, fetcher: str) -> None:
        self.csv_group.setVisible(fetcher in _CSV_FETCHERS)
        keys = _output_keys_for(fetcher)
        for row in range(self.mapping_table.rowCount()):
            key_w = self.mapping_table.cellWidget(row, 0)
            if isinstance(key_w, QComboBox):
                prev = key_w.currentText()
                key_w.blockSignals(True)
                key_w.clear()
                key_w.addItems(keys)
                key_w.setEditable(True)
                idx = key_w.findText(prev)
                if idx >= 0:
                    key_w.setCurrentIndex(idx)
                else:
                    key_w.setCurrentText(prev)
                key_w.blockSignals(False)

    def _on_mask_mode_changed(self, mode: str) -> None:
        is_tag = mode == "tag"
        self.mask_class_edit.setEnabled(is_tag)
        self.mask_tag_edit.setEnabled(is_tag)
        self.mask_placeholder_edit.setEnabled(not is_tag)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV dictionary",
            self.csv_path_edit.text() or "",
            "CSV files (*.csv);;All files (*)",
        )
        if path:
            self.csv_path_edit.setText(path)

    def _add_mapping_row(self, output_key: str = "", field_name: str = "") -> None:
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        keys = _output_keys_for(self.fetcher_combo.currentText())

        key_combo = QComboBox()
        key_combo.setEditable(True)
        key_combo.addItems(keys)
        if output_key:
            idx = key_combo.findText(output_key)
            if idx >= 0:
                key_combo.setCurrentIndex(idx)
            else:
                key_combo.setCurrentText(output_key)
        self.mapping_table.setCellWidget(row, 0, key_combo)

        field_combo = QComboBox()
        field_combo.addItem("(skip)")
        field_combo.addItems(self._note_fields)
        if field_name:
            idx = field_combo.findText(field_name)
            field_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mapping_table.setCellWidget(row, 1, field_combo)

        for col in range(2):
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.mapping_table.setItem(row, col, item)

    def _remove_mapping_row(self) -> None:
        row = self.mapping_table.currentRow()
        if row >= 0:
            self.mapping_table.removeRow(row)

    def _fill_fetcher_keys(self) -> None:
        existing = set()
        for row in range(self.mapping_table.rowCount()):
            w = self.mapping_table.cellWidget(row, 0)
            if isinstance(w, QComboBox):
                existing.add(w.currentText().strip())
        for key in _output_keys_for(self.fetcher_combo.currentText()):
            if key not in existing:
                self._add_mapping_row(key, "")


class SourceDetailDialog(QDialog):
    def __init__(self, source: dict, parent: Optional[QWidget] = None, title: str = ""):
        super().__init__(parent)
        _as_independent_window(self)
        self.setWindowTitle(title or f"Edit source — {source.get('name', '')}")
        self.resize(560, 720)
        layout = QVBoxLayout(self)
        self.editor = RowConfigWidget()
        self.editor.load_source(source)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_source(self) -> dict:
        return self.editor.result_source()


# ---------------------------------------------------------------------------
# Overview dialog
# ---------------------------------------------------------------------------

class OverviewTable(QTableWidget):
    COLUMNS = ["Deck", "Note Type", "Display Name"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)

    def set_sources(self, sources: list[dict]) -> None:
        self.setRowCount(0)
        for src in sources:
            self.append_source(src)

    def append_source(self, src: dict) -> int:
        row = self.rowCount()
        self.insertRow(row)
        values = [
            src.get("deck") or _ANY_DECK,
            src.get("note_type") or "",
            src.get("name") or src.get("fetcher") or "",
        ]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setItem(row, col, item)
        self.setRowHeight(row, 28)
        return row

    def update_row(self, row: int, src: dict) -> None:
        if not (0 <= row < self.rowCount()):
            return
        values = [
            src.get("deck") or _ANY_DECK,
            src.get("note_type") or "",
            src.get("name") or src.get("fetcher") or "",
        ]
        for col, text in enumerate(values):
            item = self.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.setItem(row, col, item)
            item.setText(text)

    def remove_current_row(self) -> int:
        row = self.currentRow()
        if row < 0:
            return -1
        self.removeRow(row)
        return row


class ConfigDialog(QDialog):
    """Main QuickFill config window."""

    def __init__(self, parent: Optional[QWidget] = None):
        # Parent None → true top-level; avoids WM grouping with the main window.
        super().__init__(parent)
        _as_independent_window(self)
        self.setWindowTitle("QuickFill configuration")
        self.resize(720, 420)

        self._base_config = _load_raw_config()
        self.sources: list[dict] = sources_from_config(self._base_config)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Sources by deck and note type. Double-click a row (or Edit…) "
                "to change identity, fetcher, mapping, and mask settings."
            )
        )

        self.table = OverviewTable()
        self.table.set_sources(self.sources)
        self.table.doubleClicked.connect(self._edit_current)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add source…")
        add_btn.clicked.connect(self._add_source)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_row)
        edit_btn = QPushButton("Edit source…")
        edit_btn.clicked.connect(self._edit_current)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_source(self) -> None:
        blank = {
            "deck": _ANY_DECK,
            "note_type": (_note_type_names() or ["Basic"])[0],
            "name": "New source",
            "fetcher": (_fetcher_names() or ["local_csv"])[0],
            "source_field": 0,
            "mapping": {},
            "config": {},
            "mask_fields": [],
            "mask_mode": "tag",
            "mask_class": "qf-headword",
        }
        dlg = SourceDetailDialog(blank, self, title="Add source")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        src = dlg.result_source()
        self.sources.append(src)
        row = self.table.append_source(src)
        self.table.selectRow(row)

    def _remove_row(self) -> None:
        row = self.table.remove_current_row()
        if row >= 0 and row < len(self.sources):
            del self.sources[row]

    def _edit_current(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.sources):
            QMessageBox.information(self, "Edit source", "Select a row first.")
            return
        dlg = SourceDetailDialog(self.sources[row], self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.result_source()
            self.sources[row] = updated
            self.table.update_row(row, updated)

    def _save_and_close(self) -> None:
        cfg = sources_to_config(self.sources, self._base_config)
        _save_raw_config(cfg)
        # Keep in-memory module config in sync for the rest of the session
        try:
            from . import quickfill_addon

            quickfill_addon.CONFIG = cfg
            quickfill_addon._selected_source.clear()
        except Exception:
            pass
        self.accept()


def open_config() -> None:
    """Entry point for Tools → QuickFill configuration…"""
    # Keep a reference so a non-modal window is not garbage-collected.
    global _config_dialog
    existing = globals().get("_config_dialog")
    if existing is not None:
        try:
            if existing.isVisible():
                existing.raise_()
                existing.activateWindow()
                return
        except RuntimeError:
            pass
    dlg = ConfigDialog(None)
    _config_dialog = dlg
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
