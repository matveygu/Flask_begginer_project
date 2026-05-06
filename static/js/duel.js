// Duel client — best-of-3 dice/slots with async polling

(function () {
    var arena = document.querySelector('.duel-arena');
    if (!arena) return;

    var duelId      = arena.dataset.duel;
    var mode        = arena.dataset.mode;
    var status      = arena.dataset.status;
    var iamChlng    = arena.dataset.iamChallenger === '1';
    var csrf        = document.querySelector('meta[name="csrf-token"]').content;
    var lastRound   = parseInt(arena.dataset.currentRound, 10) || 1;

    var pollTimer = null;

    function setStatus(role, text, played) {
        var el = document.getElementById('status-' + role);
        if (el) el.textContent = text;
        var fId = role === 'challenger' ? 'fighter-c' : 'fighter-t';
        var f = document.getElementById(fId);
        if (f) f.classList.toggle('has-played', !!played);
    }

    function setWins(c, t) {
        var ec = document.getElementById('wins-c');
        var et = document.getElementById('wins-t');
        if (ec) ec.textContent = c;
        if (et) et.textContent = t;
    }

    function showRoundOverlay(round, cScore, tScore, winner) {
        var ov    = document.getElementById('round-overlay');
        var title = document.getElementById('ro-title');
        var scores= document.getElementById('ro-scores');
        var msg   = document.getElementById('ro-msg');
        if (!ov) return;
        title.textContent  = 'Раунд ' + round + ' завершён';
        scores.innerHTML = '<span class="ro-c ' + (winner === 'challenger' ? 'ro-win' : winner === 'target' ? 'ro-lose' : '') + '">' + cScore + '</span>'
                         + '<span class="ro-vs">vs</span>'
                         + '<span class="ro-t ' + (winner === 'target' ? 'ro-win' : winner === 'challenger' ? 'ro-lose' : '') + '">' + tScore + '</span>';
        msg.textContent = winner === 'tie' ? 'Ничья в раунде'
                       : winner === 'challenger' ? 'Раунд за челленджером' : 'Раунд за соперником';
        ov.hidden = false;
        ov.classList.add('visible');
    }

    function hideRoundOverlay() {
        var ov = document.getElementById('round-overlay');
        if (!ov) return;
        ov.classList.remove('visible');
        setTimeout(function () { ov.hidden = true; }, 300);
    }

    // ── Mode pick ──
    document.querySelectorAll('.duel-mode-card').forEach(function (btn) {
        btn.addEventListener('click', async function () {
            var picked = btn.dataset.mode;
            document.querySelectorAll('.duel-mode-card').forEach(function (b) { b.disabled = true; });
            btn.classList.add('is-picked');
            var fd = new FormData();
            fd.append('csrf_token', csrf);
            fd.append('mode', picked);
            try {
                var res  = await fetch('/duel/' + duelId + '/choose', { method: 'POST', body: fd });
                var data = await res.json();
                if (data.error) { alert(data.error); document.querySelectorAll('.duel-mode-card').forEach(function (b) { b.disabled = false; }); return; }
                window.location.reload();
            } catch (e) {
                alert('Ошибка соединения');
                document.querySelectorAll('.duel-mode-card').forEach(function (b) { b.disabled = false; });
            }
        });
    });

    // ── Dice ──
    function bindDice() {
        var diceBtn = document.getElementById('dice-roll-btn');
        if (!diceBtn) return;
        diceBtn.addEventListener('click', async function () {
            diceBtn.disabled = true;
            diceBtn.textContent = '🎲 Бросаем...';
            var face = document.getElementById('duel-dice-face');
            var inner = face ? face.querySelector('.dice-side') : null;
            if (face) face.classList.add('rolling');
            var anim = inner ? setInterval(function () {
                inner.textContent = String(1 + Math.floor(Math.random() * 6));
            }, 70) : null;

            var fd = new FormData();
            fd.append('csrf_token', csrf);
            try {
                var res  = await fetch('/duel/' + duelId + '/play', { method: 'POST', body: fd });
                var data = await res.json();
                setTimeout(function () {
                    if (anim) clearInterval(anim);
                    if (face) face.classList.remove('rolling');
                    if (data.error) {
                        alert(data.error);
                        diceBtn.disabled = false;
                        diceBtn.textContent = 'Бросить';
                        return;
                    }
                    if (inner) inner.textContent = data.result.score;
                    setStatus(iamChlng ? 'challenger' : 'target', '✓ ход сделан', true);
                    handlePlayResponse(data);
                }, 900);
            } catch (e) {
                if (anim) clearInterval(anim);
                if (face) face.classList.remove('rolling');
                alert('Ошибка соединения');
                diceBtn.disabled = false;
                diceBtn.textContent = 'Бросить';
            }
        });
    }
    bindDice();

    // ── Slots ──
    var SYMBOLS   = ['0_hourglass', '0_telephone', '0_diamond', '0_floppy', '0_seven'];
    var BASE      = '/static/images/slots/';
    var CELL_H    = 80;
    var ROWS      = 3;
    var EXTRAS    = [10, 20, 30, 40, 50];
    var DURATIONS = [1.0, 1.5, 2.0, 2.5, 3.0];

    function randSym() { return SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)]; }
    function makeCell(sym) {
        var d = document.createElement('div');
        d.dataset.sym = sym;
        var img = document.createElement('img');
        img.src = BASE + sym + '.png';
        img.alt = sym;
        d.appendChild(img);
        return d;
    }
    function addItems(col, n) { for (var i = 0; i < n; i++) col.prepend(makeCell(randSym())); }

    function bindSlots() {
        var slotsBtn = document.getElementById('slots-spin-btn');
        if (!slotsBtn) return;
        document.querySelectorAll('.duel-slot-machine .column').forEach(function (col) {
            // clear existing extras and seed visible 3
            col.innerHTML = '';
            col.style.transition = 'none';
            col.style.bottom     = '0px';
            addItems(col, ROWS);
        });

        slotsBtn.addEventListener('click', async function () {
            slotsBtn.disabled = true;
            slotsBtn.textContent = '⏳ Крутим...';

            var cols = Array.from(document.querySelectorAll('.duel-slot-machine .column'));
            cols.forEach(function (col, i) {
                addItems(col, EXTRAS[i]);
                var n    = col.querySelectorAll('div').length;
                var dist = (n - ROWS) * CELL_H;
                col.style.transition = DURATIONS[i] + 's ease-out';
                col.style.bottom     = '-' + dist + 'px';
            });

            await new Promise(function (resolve) {
                cols[cols.length - 1].addEventListener('transitionend', resolve, { once: true });
            });

            var symbols = cols.map(function (col) {
                var items = col.querySelectorAll('div');
                return [items[0].dataset.sym, items[1].dataset.sym, items[2].dataset.sym];
            });

            cols.forEach(function (col) {
                Array.from(col.querySelectorAll('div')).slice(ROWS).forEach(function (el) { el.remove(); });
                col.style.transition = 'none';
                col.style.bottom     = '0px';
            });

            try {
                var res  = await fetch('/duel/' + duelId + '/play', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body:    JSON.stringify({ symbols: symbols }),
                });
                var data = await res.json();
                if (data.error) {
                    alert(data.error);
                    slotsBtn.disabled = false;
                    slotsBtn.textContent = '▶ Вращать';
                    return;
                }
                var scoreSpan = document.getElementById('slots-score');
                if (scoreSpan) scoreSpan.textContent = data.result.score;
                setStatus(iamChlng ? 'challenger' : 'target', '✓ ход сделан', true);
                handlePlayResponse(data);
            } catch (e) {
                alert('Ошибка соединения');
                slotsBtn.disabled = false;
                slotsBtn.textContent = '▶ Вращать';
            }
        });
    }
    bindSlots();

    // ── Handle play response: round-done or duel-done ──
    function handlePlayResponse(data) {
        if (data.round_done && data.round_result) {
            setWins(data.challenger_wins, data.target_wins);
            showRoundOverlay(
                data.round_result.round,
                data.round_result.challenger_score,
                data.round_result.target_score,
                data.round_result.winner
            );
            if (data.done) {
                setTimeout(function () { window.location.reload(); }, 2500);
            } else {
                setTimeout(function () {
                    hideRoundOverlay();
                    window.location.reload();
                }, 2200);
            }
        } else {
            // I played but opponent hasn't yet
            replacePlayUiWithWait();
            startPolling();
        }
    }

    function replacePlayUiWithWait() {
        var diceCtl  = document.getElementById('dice-control');
        var slotsCtl = document.getElementById('slots-control');
        var html     = '<div class="duel-wait-line">⏳ Ожидаем ход соперника...</div>';
        if (diceCtl)  diceCtl.innerHTML  = html;
        if (slotsCtl) slotsCtl.innerHTML = html;
    }

    // ── Polling ──
    function startPolling() {
        if (pollTimer) return;
        pollTimer = setInterval(checkState, 2500);
    }

    async function checkState() {
        try {
            var res  = await fetch('/duel/' + duelId + '/state');
            var data = await res.json();
            if (data.error) return;

            // Update status text + scoreboard
            setWins(data.challenger_wins, data.target_wins);
            setStatus('challenger',
                data.challenger_history.length >= data.current_round || (data.status === 'accepted' && data.challenger_score === null && data.target_score === null) ? 'ждёт хода' :
                (data.challenger_score !== null ? '✓ ход сделан' : 'ждёт хода'),
                data.challenger_score !== null || data.challenger_history.length >= data.current_round
            );
            setStatus('target',
                (data.target_score !== null ? '✓ ход сделан' : 'ждёт хода'),
                data.target_score !== null || data.target_history.length >= data.current_round
            );

            // Round transitioned — server has resolved a round and reset scores
            if (data.current_round !== lastRound || data.status === 'resolved') {
                clearInterval(pollTimer); pollTimer = null;
                // Show last completed round overlay if available
                var hist = data.challenger_history;
                var thist = data.target_history;
                if (hist.length > 0 && thist.length > 0) {
                    var lastIdx = hist.length - 1;
                    var c = hist[lastIdx];
                    var t = thist[lastIdx];
                    var winner = c > t ? 'challenger' : t > c ? 'target' : 'tie';
                    showRoundOverlay(lastIdx + 1, c, t, winner);
                }
                setTimeout(function () { window.location.reload(); }, 1800);
                return;
            }
        } catch (e) { /* ignore */ }
    }

    // Auto-poll if I've already played (waiting on opponent)
    if (status === 'accepted' && mode) {
        if (document.getElementById('dice-wait-text') || document.getElementById('slots-wait-text')) {
            startPolling();
        }
    }

    // Poll while waiting for opponent to pick mode
    if (status === 'accepted' && !mode) {
        setInterval(async function () {
            try {
                var res  = await fetch('/duel/' + duelId + '/state');
                var data = await res.json();
                if (data.mode) window.location.reload();
            } catch (e) { /* ignore */ }
        }, 4000);
    }
})();
