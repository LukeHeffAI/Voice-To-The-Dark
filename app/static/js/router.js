/**
 * VTTDRouter — Client-side AJAX router for persistent audio playback.
 *
 * Intercepts internal link clicks, fetches the target page, and swaps
 * only the #page-content and #page-styles elements so the <audio> element
 * and mini-player bar survive navigation.
 */
(function () {
    'use strict';

    var navigating = false;

    function shouldIntercept(anchor) {
        if (!anchor || !anchor.href) return false;
        // Skip external links
        if (anchor.origin !== location.origin) return false;
        // Skip download links
        if (anchor.hasAttribute('download')) return false;
        if (anchor.pathname.startsWith('/download/')) return false;
        // Skip target="_blank" or other targets
        if (anchor.target && anchor.target !== '_self') return false;
        // Skip hash-only links
        if (anchor.pathname === location.pathname && anchor.hash) return false;
        // Skip links explicitly marked to bypass router
        if (anchor.dataset.noRouter !== undefined) return false;
        return true;
    }

    function executeScripts(container) {
        var scripts = container.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            var old = scripts[i];
            var el = document.createElement('script');
            if (old.src) {
                el.src = old.src;
            } else {
                el.textContent = old.textContent;
            }
            // Copy attributes
            for (var j = 0; j < old.attributes.length; j++) {
                var attr = old.attributes[j];
                if (attr.name !== 'src') {
                    el.setAttribute(attr.name, attr.value);
                }
            }
            old.parentNode.replaceChild(el, old);
        }
    }

    function navigate(url, opts) {
        opts = opts || {};
        if (navigating) return;
        navigating = true;

        // Dispatch unload event so current page scripts can clean up
        window.dispatchEvent(new CustomEvent('page:unload'));

        fetch(url, { credentials: 'same-origin' })
            .then(function (resp) {
                // If we got redirected to a different origin (e.g. login), do full nav
                if (resp.redirected && new URL(resp.url).origin !== location.origin) {
                    location.href = resp.url;
                    return null;
                }
                return resp.text();
            })
            .then(function (html) {
                if (html === null) return;

                var parser = new DOMParser();
                var doc = parser.parseFromString(html, 'text/html');

                // Extract and swap page content
                var newContent = doc.getElementById('page-content');
                var liveContent = document.getElementById('page-content');
                if (newContent && liveContent) {
                    liveContent.innerHTML = newContent.innerHTML;
                    executeScripts(liveContent);
                }

                // Extract and swap page-specific styles
                var newStyles = doc.getElementById('page-styles');
                var liveStyles = document.getElementById('page-styles');
                if (newStyles && liveStyles) {
                    liveStyles.textContent = newStyles.textContent;
                }

                // Extract and execute page-specific scripts.
                // NOTE: We intentionally use innerHTML here because #page-scripts contains
                // <script> tags that must be preserved so executeScripts() can execute them.
                // The fetched HTML comes from the same origin (see fetch() options and redirect
                // check above), is served over HTTPS in production, and is subject to the
                // application's server-side sanitization and CSP. As a result, #page-scripts
                // is treated as trusted, first-party content in this deployment context.
                // NOTE: Unlike #page-styles which holds plain text inside a single <style> tag
                // (updated via textContent), #page-scripts holds one or more <script> tags whose
                // structure must be preserved, so innerHTML is required here.
                var newScripts = doc.getElementById('page-scripts');
                var liveScripts = document.getElementById('page-scripts');
                if (newScripts && liveScripts) {
                    // Replace the old container entirely so that any closures and event
                    // listeners associated with it can be garbage-collected instead of
                    // accumulating across navigations.
                    var newLiveScripts = liveScripts.cloneNode(false); // keep id/attributes, drop children
                    newLiveScripts.innerHTML = newScripts.innerHTML;
                    liveScripts.parentNode.replaceChild(newLiveScripts, liveScripts);
                    executeScripts(newLiveScripts);
                }

                // Update title
                var newTitle = doc.querySelector('title');
                if (newTitle) {
                    document.title = newTitle.textContent;
                }

                // Update URL
                if (opts.replace) {
                    history.replaceState({ vttdRouter: true }, '', url);
                } else {
                    history.pushState({ vttdRouter: true }, '', url);
                }

                // Scroll to top
                window.scrollTo(0, 0);

                // Dispatch load event for new page scripts
                window.dispatchEvent(new CustomEvent('page:load'));

                navigating = false;
            })
            .catch(function (err) {
                console.error('[VTTDRouter] Navigation failed, falling back:', err);
                location.href = url;
            });
    }

    function init() {
        // Replace initial state so popstate works correctly
        history.replaceState({ vttdRouter: true }, '', location.href);

        // Intercept link clicks via delegation
        document.addEventListener('click', function (e) {
            // Find the closest <a> ancestor
            var anchor = e.target.closest('a');
            if (!anchor) return;
            if (!shouldIntercept(anchor)) return;
            // Skip if modifier keys are held (open in new tab, etc.)
            if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

            e.preventDefault();
            navigate(anchor.href);
        });

        // Handle browser back/forward
        window.addEventListener('popstate', function (e) {
            navigate(location.href, { replace: true });
        });
    }

    window.VTTDRouter = {
        init: init,
        navigate: navigate,
        reload: function () {
            navigate(location.href, { replace: true });
        }
    };

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
