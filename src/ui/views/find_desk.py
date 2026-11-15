import Cocoa
import objc
from AppKit import (
    NSView, NSColor, NSScrollView, NSTableView, NSTableColumn, NSBezelBorder,
    NSProgressIndicator, NSProgressIndicatorStyleSpinning, NSControlSizeSmall,
    NSTableViewFirstColumnOnlyAutoresizingStyle, NSViewWidthSizable,
)
from Foundation import NSMakeRect, NSIndexSet

import constants
from constants import LOGGER
from control.pairing import PairingStep
from ui import theme


FIND_DESK_WIDTH = 390
FIND_DESK_HEIGHT = 296

MARGIN = 20
STATUS_COLUMN_WIDTH = 90

NO_DESKS_HINT = (
    "No desks found yet. Make sure the desk has power and isn't connected to "
    "another device, like a phone."
)


def _name(desk):
    return desk.name or "Unnamed desk"


def _status(desk):
    """Caption for the status column of a listed desk."""
    if desk.connected:
        return "Connected"
    if desk.paired is None:
        return ""
    return "Paired" if desk.paired else "Not paired"


class FindDeskView(NSView):
    """
    Content of the Find Desk window: scans for desks nearby for as long as the
    window is open and pairs with the selected one. A paired desk is handed to
    the app, which makes it the configured desk and connects. Doubles as the
    window's delegate so a running scan or pairing attempt ends with it.
    """

    def initWithApp_(self, app):
        self = objc.super(FindDeskView, self).init()
        if self is None:
            return None

        self.app = app
        self._desks = []
        self._scan = None  # future of the running scan
        self._pairing = None  # future of the running pairing attempt
        self._closed = False
        frame = NSMakeRect(0, 0, FIND_DESK_WIDTH, FIND_DESK_HEIGHT)
        self = self.initWithFrame_(frame)
        self.buildUI()

        return self

    def buildUI(self):
        """Hint, desk list, status line and the Cancel/Pair buttons."""
        inner = FIND_DESK_WIDTH - 2 * MARGIN

        hint_h = 32
        hint_y = FIND_DESK_HEIGHT - MARGIN - hint_h
        self.addSubview_(theme.label(
            "Hold the Bluetooth button on your desk's control panel until its "
            "light blinks, then select the desk below.",
            NSMakeRect(MARGIN, hint_y, inner, hint_h),
            size=12, color=NSColor.secondaryLabelColor(),
        ))

        table_h = 120
        table_y = hint_y - 10 - table_h
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(MARGIN, table_y, inner, table_h)
        )
        scroll.setBorderType_(NSBezelBorder)
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        self.table = self._table_(scroll.contentSize().width, table_h)
        scroll.setDocumentView_(self.table)
        self.addSubview_(scroll)

        # Status line: a spinner while scanning or pairing, the outcome after
        status_h = 46
        status_y = table_y - 10 - status_h
        self.spinner = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(MARGIN, status_y + status_h - 16, 16, 16)
        )
        self.spinner.setStyle_(NSProgressIndicatorStyleSpinning)
        self.spinner.setControlSize_(NSControlSizeSmall)
        self.spinner.setDisplayedWhenStopped_(False)
        self.addSubview_(self.spinner)
        self.status_label = theme.label(
            "", NSMakeRect(MARGIN + 22, status_y, inner - 22, status_h), size=12,
        )
        self.addSubview_(self.status_label)

        cancel_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(186, 18, 88, 30))
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(1)
        cancel_button.setKeyEquivalent_("\x1b")  # Escape
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        self.addSubview_(cancel_button)

        self.pair_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(282, 18, 88, 30))
        self.pair_button.setTitle_("Pair")
        self.pair_button.setBezelStyle_(1)
        self.pair_button.setKeyEquivalent_("\r")
        self.pair_button.setTarget_(self)
        self.pair_button.setAction_("pair:")
        self.pair_button.setEnabled_(False)
        self.addSubview_(self.pair_button)

    @objc.python_method
    def _table_(self, width, height):
        """Builds the desk list: a name column taking the free width and a
        fixed status column, without a header. This view is its data source."""
        table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        table.setAutoresizingMask_(NSViewWidthSizable)
        table.setColumnAutoresizingStyle_(NSTableViewFirstColumnOnlyAutoresizingStyle)
        spacing = table.intercellSpacing().width
        for identifier, column_width, align in (
            ("name", width - STATUS_COLUMN_WIDTH - 2 * spacing, theme.ALIGN_LEFT),
            ("status", STATUS_COLUMN_WIDTH, theme.ALIGN_RIGHT),
        ):
            column = NSTableColumn.alloc().initWithIdentifier_(identifier)
            column.setWidth_(column_width)
            column.dataCell().setAlignment_(align)
            table.addTableColumn_(column)
        table.setHeaderView_(None)
        table.setRowHeight_(24)
        table.setDataSource_(self)
        table.setDelegate_(self)
        table.setTarget_(self)
        table.setDoubleAction_("pair:")
        return table

    def viewDidMoveToWindow(self):
        if self.window() is not None:
            self._setStatus("Scanning for desks…", busy=True)
            self._startScan()

    def windowWillClose_(self, notification):
        """Window delegate: a scan or pairing attempt still running ends here."""
        self._closed = True
        for future in (self._scan, self._pairing):
            if future is not None:
                future.cancel()

    # --- Scanning ---

    @objc.python_method
    def _startScan(self):
        self._scan = self.app.desk.discover_desks(
            self._scanEnded, on_found=self._deskFound,
            simulated=constants.CONFIG_UUID.strip().lower() == constants.MOCK_ADDRESS,
        )

    @objc.python_method
    def _deskFound(self, desk):
        """Lists a desk the scan reports, or refreshes its entry when a later
        scan round reports it again."""
        if self._closed:
            return
        known = next(
            (i for i, listed in enumerate(self._desks) if listed.address == desk.address),
            None,
        )
        if known is None:
            self._desks.append(desk)
        else:
            self._desks[known] = desk
        self._reload()

    @objc.python_method
    def _scanEnded(self, desks, error):
        """A scan round is over: keep looking while the window is open, unless
        Bluetooth can't be used at all."""
        if self._closed:
            return
        self._scan = None
        if error:
            self._setStatus(error, busy=False)
            return
        if not self._desks:
            self._setStatus(NO_DESKS_HINT, busy=True)
        self._startScan()

    # --- Pairing ---

    def pair_(self, sender):
        desk = self._selectedDesk()
        if desk is None or self._pairing is not None:
            return
        LOGGER.debug(f"Pair button pressed for {desk.address}")
        if self._scan is not None:
            self._scan.cancel()
            self._scan = None
        self._pairing = self.app.desk.pair_desk(
            desk, self._pairingEnded, on_step=lambda step: self._pairingStep(desk, step)
        )
        self.table.setEnabled_(False)
        self._refreshPairButton()

    @objc.python_method
    def _pairingStep(self, desk, step):
        name = _name(desk)
        if step == PairingStep.CONNECTING:
            self._setStatus(f"Connecting to {name}…", busy=True)
        elif step == PairingStep.PAIRING:
            self._setStatus(
                f"Connected to {name}. Checking the desk…" if desk.paired else
                f"Waiting for macOS to pair with {name}. Accept the request if it shows one.",
                busy=True,
            )

    @objc.python_method
    def _pairingEnded(self, result):
        if self._closed:
            return
        self._pairing = None
        if result.ok:
            self.app.deskPaired(result.desk.address)
            self.window().close()
            return
        self._setStatus(result.error, busy=False)
        self.table.setEnabled_(True)
        self._refreshPairButton()
        self._startScan()

    def cancel_(self, sender):
        self.window().close()

    # --- Desk list ---

    def numberOfRowsInTableView_(self, table):
        return len(self._desks)

    def tableView_objectValueForTableColumn_row_(self, table, column, row):
        desk = self._desks[row]
        return _status(desk) if column.identifier() == "status" else _name(desk)

    def tableViewSelectionDidChange_(self, notification):
        self._refreshPairButton()

    @objc.python_method
    def _selectedDesk(self):
        row = self.table.selectedRow()
        return self._desks[row] if 0 <= row < len(self._desks) else None

    @objc.python_method
    def _reload(self):
        """Redraws the list; the first desk found is selected right away."""
        self.table.reloadData()
        if self._desks and self.table.selectedRow() < 0:
            self.table.selectRowIndexes_byExtendingSelection_(
                NSIndexSet.indexSetWithIndex_(0), False
            )
        self._refreshPairButton()

    @objc.python_method
    def _refreshPairButton(self):
        """Pair needs a selected desk and no attempt running; a desk that is
        paired already only has its connection checked, so it reads Connect."""
        desk = self._selectedDesk()
        self.pair_button.setEnabled_(desk is not None and self._pairing is None)
        self.pair_button.setTitle_("Connect" if desk is not None and desk.paired else "Pair")

    @objc.python_method
    def _setStatus(self, text, busy):
        self.status_label.setStringValue_(text)
        if busy:
            self.spinner.startAnimation_(None)
        else:
            self.spinner.stopAnimation_(None)
