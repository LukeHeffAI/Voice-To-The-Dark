/**
 * PlayerCore — Global audio player manager.
 *
 * Manages a single persistent <audio> element, playback state,
 * position saving, speed control, and MediaSession integration.
 * UI components (mini-player, full player page) subscribe to events.
 */
(function () {
    'use strict';

    var listeners = {};
    var saveTimer = null;

    var PC = {
        audio: null,
        storyId: null,
        title: '',
        author: '',

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
                try { fns[i](data); } catch (e) { console.error('[PlayerCore]', e); }
            }
        },

        // ── Track loading ──────────────────────────────────
        loadTrack: function (storyId, title, author, opts) {
            opts = opts || {};
            var self = this;

            // If already playing this track, just emit for UI sync
            if (this.storyId === storyId && this.audio.src) {
                this.emit('trackchange', { storyId: storyId, title: title, author: author });
                if (opts.autoplay && this.audio.paused) {
                    this.audio.play().catch(function () {});
                }
                return;
            }

            // Save position of previous track
            this.savePosition();

            this.storyId = storyId;
            this.title = title || '';
            this.author = author || '';

            // Persist current track info for page-reload recovery
            try {
                localStorage.setItem('vttd_current_track', JSON.stringify({
                    storyId: storyId, title: this.title, author: this.author
                }));
            } catch (e) {}

            // Set source and load
            this.audio.src = '/stream/' + storyId;
            this.audio.load();

            // Restore playback speed
            var savedSpeed = parseFloat(localStorage.getItem('vttd_playback_speed'));
            if (savedSpeed && savedSpeed >= 0.5 && savedSpeed <= 3) {
                this.audio.playbackRate = savedSpeed;
            }

            // Fetch resume position and then optionally play
            this._fetchResumePosition(storyId, function (pos) {
                if (pos > 0 && self.storyId === storyId) {
                    self.audio.currentTime = pos;
                }
                if (opts.autoplay) {
                    self.audio.play().catch(function () {});
                }
            });

            this.setupMediaSession();
            this.emit('trackchange', { storyId: storyId, title: this.title, author: this.author });
        },

        _fetchResumePosition: function (storyId, cb) {
            fetch('/stories/playback/' + storyId, { credentials: 'same-origin' })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    cb(data ? data.position_seconds || 0 : 0);
                })
                .catch(function () { cb(0); });
        },

        // ── Playback controls ──────────────────────────────
        play: function () {
            this.audio.play().catch(function () {});
        },

        pause: function () {
            this.audio.pause();
        },

        togglePlay: function () {
            if (this.audio.paused) {
                this.play();
            } else {
                this.pause();
            }
        },

        seek: function (time) {
            this.audio.currentTime = Math.max(0, Math.min(time, this.audio.duration || 0));
            this.updatePositionState();
        },

        skip: function (seconds) {
            this.seek(this.audio.currentTime + seconds);
        },

        setPlaybackSpeed: function (rate) {
            rate = Math.max(0.5, Math.min(3, parseFloat(rate) || 1));
            rate = Math.round(rate * 20) / 20;
            this.audio.playbackRate = rate;
            try { localStorage.setItem('vttd_playback_speed', rate); } catch (e) {}
            this.updatePositionState();
            this.emit('speedchange', rate);
        },

        // ── Position saving ────────────────────────────────
        savePosition: function () {
            if (!this.storyId) return;
            if (!this.audio.currentTime || this.audio.currentTime < 1) return;
            var body = JSON.stringify({
                story_id: this.storyId,
                position_seconds: Math.floor(this.audio.currentTime)
            });
            try {
                navigator.sendBeacon(
                    '/stories/playback',
                    new Blob([body], { type: 'application/json' })
                );
            } catch (e) {}
        },

        _startAutoSave: function () {
            this._stopAutoSave();
            var self = this;
            saveTimer = setInterval(function () { self.savePosition(); }, 15000);
        },

        _stopAutoSave: function () {
            if (saveTimer) {
                clearInterval(saveTimer);
                saveTimer = null;
            }
        },

        // ── MediaSession ───────────────────────────────────
        setupMediaSession: function () {
            if (!('mediaSession' in navigator)) return;
            var self = this;

            navigator.mediaSession.metadata = new MediaMetadata({
                title: this.title,
                artist: 'Voice In The Dark',
                album: 'NoSleep Narrations',
                artwork: [
                    { src: '/static/icon-192.png', sizes: '192x192', type: 'image/png' },
                    { src: '/static/icon-512.png', sizes: '512x512', type: 'image/png' }
                ]
            });

            var handlers = [
                ['play', function () { self.play(); }],
                ['pause', function () { self.pause(); }],
                ['seekbackward', function (d) { self.skip(-(d.seekOffset || 15)); }],
                ['seekforward', function (d) { self.skip(d.seekOffset || 15); }],
                ['seekto', function (d) {
                    if (d.fastSeek && 'fastSeek' in self.audio) self.audio.fastSeek(d.seekTime);
                    else self.audio.currentTime = d.seekTime;
                    self.updatePositionState();
                }],
                ['stop', function () { self.pause(); self.audio.currentTime = 0; self.savePosition(); }],
                ['previoustrack', function () { if (window.Playlist) Playlist.prev(); }],
                ['nexttrack', function () { if (window.Playlist) Playlist.next(); }]
            ];

            for (var i = 0; i < handlers.length; i++) {
                try {
                    navigator.mediaSession.setActionHandler(handlers[i][0], handlers[i][1]);
                } catch (e) {}
            }
        },

        updatePositionState: function () {
            if (!('mediaSession' in navigator)) return;
            if (!isFinite(this.audio.duration) || this.audio.duration <= 0) return;
            try {
                navigator.mediaSession.setPositionState({
                    duration: this.audio.duration,
                    playbackRate: this.audio.playbackRate,
                    position: Math.min(this.audio.currentTime, this.audio.duration)
                });
            } catch (e) {}
        },

        // ── Initialisation ─────────────────────────────────
        init: function () {
            var self = this;
            this.audio = document.getElementById('persistent-audio');
            if (!this.audio) {
                console.error('[PlayerCore] #persistent-audio element not found');
                return;
            }

            // Wire audio events → PlayerCore events
            this.audio.addEventListener('play', function () {
                self.emit('play');
                if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
                self._startAutoSave();
            });

            this.audio.addEventListener('pause', function () {
                self.emit('pause');
                if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
                self.savePosition();
                self._stopAutoSave();
            });

            this.audio.addEventListener('timeupdate', function () {
                self.emit('timeupdate', {
                    currentTime: self.audio.currentTime,
                    duration: self.audio.duration
                });
                self.updatePositionState();
            });

            this.audio.addEventListener('loadedmetadata', function () {
                self.emit('loadedmetadata', { duration: self.audio.duration });
            });

            this.audio.addEventListener('ended', function () {
                self.emit('ended');
                self.savePosition();
                self._stopAutoSave();
            });

            // Save on visibility change and before unload
            document.addEventListener('visibilitychange', function () {
                if (document.visibilityState === 'hidden') self.savePosition();
            });
            window.addEventListener('beforeunload', function () { self.savePosition(); });

            // Restore track info from localStorage (don't auto-load audio)
            try {
                var saved = JSON.parse(localStorage.getItem('vttd_current_track'));
                if (saved && saved.storyId) {
                    this.storyId = saved.storyId;
                    this.title = saved.title || '';
                    this.author = saved.author || '';
                    // Emit so mini-player can show (paused state)
                    this.emit('trackchange', {
                        storyId: saved.storyId,
                        title: this.title,
                        author: this.author,
                        restored: true
                    });
                }
            } catch (e) {}
        }
    };

    window.PlayerCore = PC;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { PC.init(); });
    } else {
        PC.init();
    }
})();
