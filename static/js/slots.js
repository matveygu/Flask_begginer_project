const SYMBOLS   = ['0_hourglass', '0_telephone', '0_diamond', '0_floppy', '0_seven'];
const BASE      = '/static/images/slots/';
const CELL_H    = 80;                          // px — must match CSS .column div height
const ROWS      = 3;                           // visible rows
const EXTRAS    = [10, 20, 30, 40, 50];        // items prepended per reel
const DURATIONS = [1.0, 1.5, 2.0, 2.5, 3.0]; // transition seconds per reel

let busy = false;

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.column').forEach(function (col) {
        addItems(col, ROWS);
    });
    document.getElementById('spin-button').addEventListener('click', spin);
});

// ── Helpers ───────────────────────────────────────────────────

function randSym() {
    return SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
}

function makeCell(sym) {
    var d   = document.createElement('div');
    d.dataset.sym = sym;
    var img = document.createElement('img');
    img.src = BASE + sym + '.png';
    img.alt = sym;
    d.appendChild(img);
    return d;
}

// Prepend n random cells — they appear at visual top, scroll into view
function addItems(col, n) {
    for (var i = 0; i < n; i++) {
        col.prepend(makeCell(randSym()));
    }
}

// ── Main spin flow ────────────────────────────────────────────

async function spin() {
    if (busy) return;
    busy = true;

    var bet = parseInt(document.getElementById('bet-amount').value);
    var btn = document.getElementById('spin-button');
    btn.disabled    = true;
    btn.textContent = '⏳ Крутим...';
    clearHighlights();

    var cols = Array.from(document.querySelectorAll('.column'));

    // Prepend random items to each reel, then scroll up with CSS transition
    cols.forEach(function (col, i) {
        addItems(col, EXTRAS[i]);
        var n    = col.querySelectorAll('div').length;
        var dist = (n - ROWS) * CELL_H;           // how far to scroll
        col.style.transition = DURATIONS[i] + 's ease-out';
        col.style.bottom     = '-' + dist + 'px'; // scroll column down = items move up
    });

    // Wait for the slowest reel to finish
    await new Promise(function (resolve) {
        cols[cols.length - 1].addEventListener('transitionend', resolve, { once: true });
    });

    // Read visible symbols: after scroll, items[0..2] are the ones in view
    var finalSymbols = cols.map(function (col) {
        var items = col.querySelectorAll('div');
        return [
            items[0].dataset.sym,
            items[1].dataset.sym,
            items[2].dataset.sym,
        ];
    });

    // Cleanup: remove extra items, snap position back (no animation)
    cols.forEach(function (col) {
        Array.from(col.querySelectorAll('div')).slice(ROWS).forEach(function (el) { el.remove(); });
        col.style.transition = 'none';
        col.style.bottom     = '0px';
    });

    // Send landed grid to server
    var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    var data;
    try {
        var res = await fetch('/spin', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body:    JSON.stringify({ bet: bet, symbols: finalSymbols }),
        });
        data = await res.json();
    } catch (_) {
        showErr('Ошибка соединения');
        reset(btn); return;
    }

    if (data.error) { showErr(data.error); reset(btn); return; }

    highlightWins(cols, finalSymbols);
    document.getElementById('winnings').textContent = data.winnings;
    document.getElementById('balance').textContent  = data.new_balance;

    reset(btn);
}

// ── Win highlighting ──────────────────────────────────────────

function highlightWins(cols, symbols) {
    // Collect winning (col, row) pairs — same logic as server
    var winSet = {};
    function mark(c, r) { winSet[c + ',' + r] = true; }

    // Horizontal: consecutive from left
    for (var row = 0; row < ROWS; row++) {
        var count = 1;
        for (var col = 1; col < 5; col++) {
            if (symbols[col][row] === symbols[col - 1][row]) {
                count++;
            } else {
                if (count >= 3) {
                    for (var c = col - count; c < col; c++) mark(c, row);
                }
                count = 1;
            }
        }
        if (count >= 3) {
            for (var c = 5 - count; c < 5; c++) mark(c, row);
        }
    }

    // Vertical: all 3 same in a column
    for (var col = 0; col < 5; col++) {
        if (symbols[col][0] === symbols[col][1] && symbols[col][1] === symbols[col][2]) {
            mark(col, 0); mark(col, 1); mark(col, 2);
        }
    }

    // Diagonal ↘
    for (var sc = 0; sc < 3; sc++) {
        if (symbols[sc][0] === symbols[sc + 1][1] && symbols[sc + 1][1] === symbols[sc + 2][2]) {
            mark(sc, 0); mark(sc + 1, 1); mark(sc + 2, 2);
        }
    }

    // Diagonal ↙
    for (var sc = 2; sc < 5; sc++) {
        if (symbols[sc][0] === symbols[sc - 1][1] && symbols[sc - 1][1] === symbols[sc - 2][2]) {
            mark(sc, 0); mark(sc - 1, 1); mark(sc - 2, 2);
        }
    }

    var anyWin = Object.keys(winSet).length > 0;
    if (!anyWin) return;

    cols.forEach(function (col, ci) {
        col.querySelectorAll('div').forEach(function (cell, ri) {
            if (winSet[ci + ',' + ri]) {
                cell.classList.add('win');
            } else {
                cell.classList.add('lose');
            }
        });
    });
}

// ── Utility ───────────────────────────────────────────────────

function clearHighlights() {
    document.querySelectorAll('.column div').forEach(function (cell) {
        cell.classList.remove('win', 'lose');
    });
    var w = document.getElementById('winnings');
    w.textContent = '0';
    w.style.color = '';
}

function reset(btn) {
    busy            = false;
    btn.disabled    = false;
    btn.textContent = '▶ Вращать';
}

function showErr(msg) {
    var w = document.getElementById('winnings');
    w.textContent = msg;
    w.style.color = 'var(--red, #ef4444)';
    setTimeout(function () { w.textContent = '0'; w.style.color = ''; }, 3000);
}
