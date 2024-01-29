#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# Created By  : Marcin Szczygliński                  #
# Updated Date: 2024.01.29 18:00:00                  #
# ================================================== #

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QTextEdit, QMenu, QWidget, QVBoxLayout

from pygpt_net.ui.widget.element.labels import HelpLabel
from pygpt_net.utils import trans
import pygpt_net.icons_rc


class NotepadWidget(QWidget):
    def __init__(self, window=None):
        """
        Notepad

        :param window: main window
        """
        super(NotepadWidget, self).__init__(window)
        self.window = window
        self.id = 1
        self.textarea = NotepadOutput(self.window)
        self.window.ui.nodes['tip.output.tab.notepad'] = HelpLabel(trans('tip.output.tab.notepad'), self.window)

        layout = QVBoxLayout()
        layout.addWidget(self.textarea)
        layout.addWidget(self.window.ui.nodes['tip.output.tab.notepad'])
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def setText(self, text):
        self.textarea.setText(text)

    def toPlainText(self):
        return self.textarea.toPlainText()


class NotepadOutput(QTextEdit):
    def __init__(self, window=None):
        """
        Notepad

        :param window: main window
        """
        super(NotepadOutput, self).__init__(window)
        self.window = window
        self.setAcceptRichText(False)
        self.setStyleSheet(self.window.controller.theme.style('font.chat.output'))
        self.textChanged.connect(
            lambda: self.window.controller.notepad.save(self.id))
        self.value = self.window.core.config.data['font_size']
        self.max_font_size = 42
        self.min_font_size = 8
        self.id = 1

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        selected_text = self.textCursor().selectedText()
        if selected_text:
            # plain text
            plain_text = self.textCursor().selection().toPlainText()

            # audio read
            action = QAction(QIcon(":/icons/volume.svg"), trans('text.context_menu.audio.read'), self)
            action.triggered.connect(self.audio_read_selection)
            menu.addAction(action)

            # copy to
            copy_to_menu = QMenu(trans('text.context_menu.copy_to'), self)

            # input
            action = QAction(QIcon(":/icons/more_horizontal.svg"), trans('text.context_menu.copy_to.input'), self)
            action.triggered.connect(
                lambda: self.window.controller.chat.common.append_to_input(selected_text))
            copy_to_menu.addAction(action)

            # notepad
            num_notepads = self.window.controller.notepad.get_num_notepads()
            if num_notepads > 0:
                for i in range(1, num_notepads + 1):
                    if i == self.id:
                        continue
                    name = self.window.controller.notepad.get_notepad_name(i)
                    action = QAction(QIcon(":/icons/paste.svg"), name, self)
                    action.triggered.connect(lambda checked=False, i=i:
                                             self.window.controller.notepad.append_text(selected_text, i))
                    copy_to_menu.addAction(action)

            # calendar
            action = QAction(QIcon(":/icons/calendar.svg"), trans('text.context_menu.copy_to.calendar'), self)
            action.triggered.connect(
                lambda: self.window.controller.calendar.note.append_text(selected_text))
            copy_to_menu.addAction(action)

            menu.addMenu(copy_to_menu)

            # save as (selected)
            action = QAction(QIcon(":/icons/save.svg"), trans('action.save_as'), self)
            action.triggered.connect(
                lambda: self.window.controller.chat.common.save_text(plain_text))
            menu.addAction(action)
        else:
            # save as (all)
            action = QAction(QIcon(":/icons/save.svg"), trans('action.save_as'), self)
            action.triggered.connect(
                lambda: self.window.controller.chat.common.save_text(self.toPlainText()))
            menu.addAction(action)

        menu.exec_(event.globalPos())

    def audio_read_selection(self):
        """
        Read selected text (audio)
        """
        self.window.controller.audio.read_text(self.textCursor().selectedText())

    def wheelEvent(self, event):
        """
        Wheel event: set font size

        :param event: Event
        """
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                if self.value < self.max_font_size:
                    self.value += 1
            else:
                if self.value > self.min_font_size:
                    self.value -= 1

            self.window.core.config.data['font_size'] = self.value
            self.window.core.config.save()
            option = self.window.controller.settings.editor.get_option('font_size')
            option['value'] = self.value
            self.window.controller.config.apply('config', 'font_size', option)
            self.window.controller.ui.update_font_size()
            event.accept()
        else:
            super(NotepadOutput, self).wheelEvent(event)
