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

    // Ask server FIRST — it is authoritative about the grid
    var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    var data;
    try {
        var res = await fetch('/spin', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body:    JSON.stringify({ bet: bet }),
        });
        data = await res.json();
    } catch (_) {
        showErr('Ошибка соединения');
        reset(btn); return;
    }

    if (data.error) { showErr(data.error); reset(btn); return; }

    var serverGrid = data.symbols;  // [[c0r0,c0r1,c0r2], ...]
    var cols = Array.from(document.querySelectorAll('.column'));

    // Build each reel: fluff at the bottom, server's 3 final symbols at the top.
    // After scroll by (n - ROWS) * CELL_H px, items[0..2] become visible and
    // are guaranteed to be the server-decided cells.
    cols.forEach(function (col, i) {
        addItems(col, EXTRAS[i] - ROWS);                       // visual fluff
        for (var r = ROWS - 1; r >= 0; r--) {                  // server symbols on top
            col.prepend(makeCell(serverGrid[i][r]));
        }
        var n    = col.querySelectorAll('div').length;
        var dist = (n - ROWS) * CELL_H;
        col.style.transition = DURATIONS[i] + 's ease-out';
        col.style.bottom     = '-' + dist + 'px';
    });

    await new Promise(function (resolve) {
        cols[cols.length - 1].addEventListener('transitionend', resolve, { once: true });
    });

    // Cleanup extras (keep ROWS visible)
    cols.forEach(function (col) {
        Array.from(col.querySelectorAll('div')).slice(ROWS).forEach(function (el) { el.remove(); });
        col.style.transition = 'none';
        col.style.bottom     = '0px';
    });

    highlightWins(cols, serverGrid);
    document.getElementById('winnings').textContent = data.winnings;
    if (typeof animateBalance === 'function') {
        animateBalance('balance', data.new_balance);
    } else {
        document.getElementById('balance').textContent = data.new_balance;
    }

    if (data.winnings >= bet * 5 && typeof window.fireConfetti === 'function') {
        window.fireConfetti();
    }

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
