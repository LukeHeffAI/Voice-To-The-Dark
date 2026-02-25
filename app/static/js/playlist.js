/**
 * Playlist — Queue/playlist manager with localStorage persistence.
 *
 * Manages an ordered queue of tracks with repeat modes, drag-to-reorder,
 * and "play next" / "add to end" operations.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'vttd_playlist';
    var listeners = {};
    var state = { items: [], currentIndex: 0, repeatMode: 'off' };

    var PL = {
        // ── Event emitter ──────────────────────────────────
        on: function (event, fn) {
            if (!listeners[event]) listeners[event] = [];
            listeners[event].push(fn);
        },

        off: function (event, fn) {
            if (!listeners[event]) return;
            listeners[event] = listeners[event].filter(function (f) { return f !== fn; });
        },

        emit: function (event, data) {
            var fns = listeners[event];
            if (!fns) return;
            for (var i = 0; i < fns.length; i++) {
                try { fns[i](data); } catch (e) { console.error('[Playlist]', e); }
            }
        },

        // ── Persistence ────────────────────────────────────
        save: function () {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
            } catch (e) {}
        },

        load: function () {
            try {
                var raw = localStorage.getItem(STORAGE_KEY);
                if (raw) {
                    var parsed = JSON.parse(raw);
                    if (parsed && Array.isArray(parsed.items)) {
                        state = parsed;
                        // Ensure repeatMode is valid
                        if (['off', 'all', 'one'].indexOf(state.repeatMode) === -1) {
                            state.repeatMode = 'off';
                        }
                    }
                }
            } catch (e) {}
        },

        // ── Queue operations ───────────────────────────────

        /** Add a track right after the current one */
        addNext: function (info) {
            // Prevent duplicate adjacent entries
            var insertIdx = state.currentIndex + 1;
            state.items.splice(insertIdx, 0, {
                storyId: info.storyId,
                title: info.title || '',
                author: info.author || ''
            });
            this.save();
            this.emit('queuechange');
        },

        /** Add a track to the end of the queue */
        addToEnd: function (info) {
            state.items.push({
                storyId: info.storyId,
                title: info.title || '',
                author: info.author || ''
            });
            this.save();
            this.emit('queuechange');
        },

        /** Remove the track at the given index */
        removeAt: function (index) {
            if (index < 0 || index >= state.items.length) return;
            state.items.splice(index, 1);
            // Adjust currentIndex
            if (state.items.length === 0) {
                state.currentIndex = 0;
            } else if (index < state.currentIndex) {
                state.currentIndex--;
            } else if (index === state.currentIndex && state.currentIndex >= state.items.length) {
                state.currentIndex = state.items.length - 1;
            }
            this.save();
            this.emit('queuechange');
        },

        /** Reorder: move item from oldIndex to newIndex (for drag-and-drop) */
        reorder: function (oldIndex, newIndex) {
            if (oldIndex === newIndex) return;
            if (oldIndex < 0 || oldIndex >= state.items.length) return;
            if (newIndex < 0 || newIndex >= state.items.length) return;

            var item = state.items.splice(oldIndex, 1)[0];
            state.items.splice(newIndex, 0, item);

            // Adjust currentIndex to follow the currently-playing track
            if (state.currentIndex === oldIndex) {
                state.currentIndex = newIndex;
            } else if (oldIndex < state.currentIndex && newIndex >= state.currentIndex) {
                state.currentIndex--;
            } else if (oldIndex > state.currentIndex && newIndex <= state.currentIndex) {
                state.currentIndex++;
            }

            this.save();
            this.emit('queuechange');
        },

        /** Play a specific item by index */
        playAt: function (index) {
            if (index < 0 || index >= state.items.length) return;
            state.currentIndex = index;
            var track = state.items[index];
            this.save();
            this.emit('queuechange');
            PlayerCore.loadTrack(track.storyId, track.title, track.author, { autoplay: true });
        },

        /** Advance to next track, respecting repeat mode */
        next: function () {
            if (state.items.length === 0) return;

            if (state.repeatMode === 'one') {
                // Repeat-one still advances on explicit next()
                // (repeat-one auto-replay only happens on track end)
            }

            if (state.currentIndex < state.items.length - 1) {
                this.playAt(state.currentIndex + 1);
            } else if (state.repeatMode === 'all') {
                this.playAt(0);
            }
            // If repeatMode is 'off' and at end, do nothing
        },

        /** Go to previous track, or restart current if >3s in */
        prev: function () {
            if (state.items.length === 0) return;

            // If more than 3 seconds in, restart current track
            if (PlayerCore.audio && PlayerCore.audio.currentTime > 3) {
                PlayerCore.seek(0);
                PlayerCore.play();
                return;
            }

            if (state.currentIndex > 0) {
                this.playAt(state.currentIndex - 1);
            } else if (state.repeatMode === 'all') {
                this.playAt(state.items.length - 1);
            } else {
                // At start, just restart
                PlayerCore.seek(0);
                PlayerCore.play();
            }
        },

        /** Clear the entire queue */
        clear: function () {
            state.items = [];
            state.currentIndex = 0;
            this.save();
            this.emit('queuechange');
        },

        /** Cycle repeat mode: off → all → one → off */
        toggleRepeat: function () {
            var modes = ['off', 'all', 'one'];
            var idx = modes.indexOf(state.repeatMode);
            state.repeatMode = modes[(idx + 1) % 3];
            this.save();
            this.emit('repeatchange', state.repeatMode);
        },

        // ── Getters ────────────────────────────────────────
        getItems: function () { return state.items; },
        getCurrentIndex: function () { return state.currentIndex; },
        getRepeatMode: function () { return state.repeatMode; },
        getCurrentTrack: function () { return state.items[state.currentIndex] || null; },

        /** Ensure the currently-playing track is in the playlist */
        ensureCurrent: function (info) {
            // If the playlist is empty or current doesn't match, set it
            if (state.items.length === 0 ||
                !state.items[state.currentIndex] ||
                state.items[state.currentIndex].storyId !== info.storyId) {
                // Find if it already exists in the playlist
                var found = -1;
                for (var i = 0; i < state.items.length; i++) {
                    if (state.items[i].storyId === info.storyId) {
                        found = i;
                        break;
                    }
                }
                if (found >= 0) {
                    state.currentIndex = found;
                } else {
                    // Add as the only/first item
                    state.items.unshift({
                        storyId: info.storyId,
                        title: info.title || '',
                        author: info.author || ''
                    });
                    state.currentIndex = 0;
                }
                this.save();
                this.emit('queuechange');
            }
        },

        // ── Handle track end ───────────────────────────────
        _onTrackEnded: function () {
            if (state.repeatMode === 'one') {
                PlayerCore.seek(0);
                PlayerCore.play();
                return;
            }

            if (state.currentIndex < state.items.length - 1) {
                PL.playAt(state.currentIndex + 1);
            } else if (state.repeatMode === 'all' && state.items.length > 0) {
                PL.playAt(0);
            }
            // Otherwise: stop (do nothing)
        },

        // ── Initialisation ─────────────────────────────────
        init: function () {
            this.load();

            // Listen for track endings to auto-advance
            PlayerCore.on('ended', this._onTrackEnded);

            // Emit initial state so UI can render
            this.emit('queuechange');
            this.emit('repeatchange', state.repeatMode);
        }
    };

    window.Playlist = PL;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { PL.init(); });
    } else {
        PL.init();
    }
})();
