from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import requests

APP_VERSION = "1.2.5-alpha"

SECTION_CARD_STYLE = """
    QFrame#AboutSection {
        background-color: #1a1a1a;
        border: 1px solid #2e2e2e;
        border-radius: 8px;
    }
"""

# ── API health-check worker ──────────────────────────────────────────────────

class _StatusWorker(QThread):
    """Pings each API endpoint in the background and emits results."""
    finished = pyqtSignal(dict)  # {service_name: bool}

    ENDPOINTS = {
        "AllAnime API": "https://api.allanime.day/api",
        "AniList API": "https://graphql.anilist.co",
    }

    def run(self):
        results = {}
        for name, url in self.ENDPOINTS.items():
            try:
                resp = requests.get(url, timeout=8)
                results[name] = resp.status_code < 500
            except Exception:
                results[name] = False
        self.finished.emit(results)


# ── About View ───────────────────────────────────────────────────────────────

class AboutView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(10)

        # Title
        title = QLabel("About", self)
        title.setObjectName("ViewTitle")
        root_layout.addWidget(title)

        # Scrollable body
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body.setObjectName("AboutBody")
        body.setStyleSheet(apply_theme("""
            QWidget#AboutBody {
                background-color: #1a1a1a;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
            }
        """))
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(16, 16, 16, 16)
        self.body_layout.setSpacing(16)

        # ── Section 1: App Information ────────────────────────────────────
        info_card, info_layout = self._make_section_card("App Information")

        self._add_info_row(info_layout, "Version", APP_VERSION)
        self._add_info_row(info_layout, "Streaming Source", "AllAnime  (api.allanime.day)")
        self._add_info_row(info_layout, "Anime Metadata", "AniList  (graphql.anilist.co)")

        # Service Status sub-header
        status_header = QLabel("Service Status", info_card)
        status_header.setStyleSheet(apply_theme(
            "color: #e8e8e8; font-size: 13px; font-weight: bold; "
            "margin-top: 4px; padding-left: 4px; border: none;"
        ))
        info_layout.addWidget(status_header)

        self.status_labels: dict[str, QLabel] = {}
        for svc in ("AllAnime API", "AniList API"):
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(10, 0, 0, 0)

            name_label = QLabel(svc, info_card)
            name_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px; border: none;"))
            name_label.setFixedWidth(180)

            status_label = QLabel("  Checking…", info_card)
            status_label.setStyleSheet(apply_theme("color: #888888; font-size: 13px; border: none;"))
            self.status_labels[svc] = status_label

            row_layout.addWidget(name_label)
            row_layout.addWidget(status_label)
            row_layout.addStretch()
            info_layout.addLayout(row_layout)

        self.body_layout.addWidget(info_card)

        # ── Section 2: Disclaimer ─────────────────────────────────────────
        disc_card, disc_layout = self._make_section_card("Disclaimer")

        disclaimer_text = (
            "AniGUI is currently in an early alpha build. As the application is still "
            "under active development, you may encounter bugs, crashes, incomplete features, "
            "or unexpected behavior. We appreciate your patience and welcome any feedback "
            "or bug reports through the project's GitHub repository.\n\n"
            'This software is provided "as-is" without any warranty of any kind. '
            "Use it at your own discretion."
        )
        disclaimer = QLabel(disclaimer_text, disc_card)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(apply_theme(
            "color: #888888; font-size: 12px; line-height: 1.5; padding-left: 6px; border: none;"
        ))
        disc_layout.addWidget(disclaimer)

        self.body_layout.addWidget(disc_card)

        # ── Section 3: Developers ─────────────────────────────────────────
        dev_card, dev_layout = self._make_section_card("Developers")

        devs = [
            ("Charls", "Developer"),
            ("Harvey", "Developer"),
            ("Jin", "Developer"),
        ]
        for name, role in devs:
            row = QHBoxLayout()
            row.setContentsMargins(10, 0, 0, 0)

            name_lbl = QLabel(name, dev_card)
            name_lbl.setStyleSheet(apply_theme(
                "color: #c084fc; font-size: 13px; font-weight: bold; border: none;"
            ))
            name_lbl.setFixedWidth(120)

            role_lbl = QLabel(f"— {role}", dev_card)
            role_lbl.setStyleSheet(apply_theme("color: #888888; font-size: 13px; border: none;"))

            row.addWidget(name_lbl)
            row.addWidget(role_lbl)
            row.addStretch()
            dev_layout.addLayout(row)

        # GitHub link
        gh_layout = QHBoxLayout()
        gh_layout.setContentsMargins(10, 8, 0, 0)
        gh_icon = QLabel("Star on Github:", dev_card)
        gh_icon.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px; border: none;"))
        gh_link = QLabel(
            '<a href="https://github.com/Chxrls/AniGUI" '
            'style="color: #c084fc; text-decoration: none;">'
            'https://github.com/Chxrls/AniGUI</a>',
            dev_card,
        )
        gh_link.setOpenExternalLinks(True)
        gh_link.setStyleSheet(apply_theme("font-size: 13px; border: none;"))

        gh_layout.addWidget(gh_icon)
        gh_layout.addWidget(gh_link)
        gh_layout.addStretch()
        dev_layout.addLayout(gh_layout)

        self.body_layout.addWidget(dev_card)

        # Push everything up
        self.body_layout.addStretch()

        scroll.setWidget(body)
        root_layout.addWidget(scroll)

        # Fire background pings
        self._worker = _StatusWorker()
        self._worker.finished.connect(self._on_status_results)
        self._worker.start()

    # ── helpers ───────────────────────────────────────────────────────────

    def _make_section_card(self, header_text: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a rounded-corner card frame with a bold header, matching bookmarks style."""
        card = QFrame(self)
        card.setObjectName("AboutSection")
        card.setStyleSheet(apply_theme(SECTION_CARD_STYLE))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QLabel(header_text, card)
        header.setStyleSheet(apply_theme(
            "font-weight: bold; color: #e8e8e8; font-size: 14px; border: none;"
        ))
        layout.addWidget(header)

        return card, layout

    def _add_info_row(self, target_layout: QVBoxLayout, key: str, value: str):
        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 0, 0)

        k = QLabel(key, self)
        k.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px; font-weight: bold; border: none;"))
        k.setFixedWidth(180)

        v = QLabel(value, self)
        v.setStyleSheet(apply_theme("color: #888888; font-size: 13px; border: none;"))

        row.addWidget(k)
        row.addWidget(v)
        row.addStretch()
        target_layout.addLayout(row)

    def _on_status_results(self, results: dict):
        for svc, ok in results.items():
            lbl = self.status_labels.get(svc)
            if lbl is None:
                continue
            if ok:
                lbl.setText("  ● Online")
                lbl.setStyleSheet(apply_theme("color: #4ade80; font-size: 13px; border: none;"))
            else:
                lbl.setText("  ● Offline")
                lbl.setStyleSheet(apply_theme("color: #f87171; font-size: 13px; border: none;"))

    def refresh_status(self):
        """Re-ping API endpoints (called when the user navigates to About)."""
        for lbl in self.status_labels.values():
            lbl.setText("  Checking…")
            lbl.setStyleSheet(apply_theme("color: #888888; font-size: 13px; border: none;"))
        self._worker = _StatusWorker()
        self._worker.finished.connect(self._on_status_results)
        self._worker.start()
