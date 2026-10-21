// Google Analytics 4 tracking for sfhoo.com
(function () {
    var GA_ID = 'G-WQ2P9YBCG0';
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag('js', new Date());
    gtag('config', GA_ID);
    // Campaign tags (utm_source, utm_medium, utm_campaign) on incoming links
    // are picked up by GA4 automatically.

    // Entry point: which section the visitor landed on and where they came from.
    gtag('event', 'entry_point', {
        entry_section: location.hash ? location.hash.slice(1) : 'top',
        // Only the referring site's domain, never the full URL.
        entry_referrer: document.referrer ? new URL(document.referrer).hostname : '(direct)'
    });

    var SOCIAL = {
        'www.linkedin.com': 'LinkedIn', 'linkedin.com': 'LinkedIn',
        'github.com': 'GitHub',
        'twitter.com': 'X', 'x.com': 'X'
    };

    function sectionOf(node) {
        var s = node && node.closest ? node.closest('section[id]') : null;
        return s ? s.id : 'other';
    }

    document.addEventListener('DOMContentLoaded', function () {
        var hasIO = 'IntersectionObserver' in window;

        // Section reach: once per visit, per section.
        if (hasIO) {
            var reached = {};
            var secObs = new IntersectionObserver(function (entries) {
                entries.forEach(function (e) {
                    var id = e.target.id;
                    if (!e.isIntersecting || reached[id]) return;
                    reached[id] = true;
                    gtag('event', 'section_view', { section_name: id });
                    if (id === 'resume') gtag('event', 'resume_view', { method: 'scroll' });
                    secObs.unobserve(e.target);
                });
            }, { threshold: 0.25 });
            document.querySelectorAll('main section[id]').forEach(function (s) { secObs.observe(s); });
        }

        // Scroll depth: 25 / 50 / 75 / 100 percent, once each.
        var marks = [25, 50, 75, 100], hit = {};
        function onScroll() {
            var h = document.documentElement;
            var max = h.scrollHeight - window.innerHeight;
            var pct = max > 0 ? Math.round((window.scrollY / max) * 100) : 100;
            marks.forEach(function (m) {
                if (pct >= m && !hit[m]) {
                    hit[m] = true;
                    gtag('event', 'scroll_depth', { percent_scrolled: m });
                }
            });
        }
        window.addEventListener('scroll', onScroll, { passive: true });

        // Résumé reading time: counts only while the résumé is on screen and the tab is visible.
        var resume = document.getElementById('resume');
        if (resume && hasIO) {
            var onScreen = false, startedAt = 0, totalMs = 0, readSent = false, timeSent = false;
            function tick() {
                if (onScreen && startedAt) { totalMs += Date.now() - startedAt; startedAt = Date.now(); }
                if (!readSent && totalMs >= 15000) {
                    readSent = true;
                    gtag('event', 'resume_read', { seconds: 15 });
                }
            }
            new IntersectionObserver(function (entries) {
                entries.forEach(function (e) {
                    tick();
                    onScreen = e.isIntersecting && !document.hidden;
                    startedAt = onScreen ? Date.now() : 0;
                });
            }, { threshold: 0.2 }).observe(resume);
            setInterval(tick, 1000);
            function flush() {
                tick();
                if (!timeSent && totalMs >= 1000) {
                    timeSent = true;
                    gtag('event', 'resume_time', {
                        seconds: Math.round(totalMs / 1000),
                        transport_type: 'beacon'
                    });
                }
            }
            document.addEventListener('visibilitychange', function () {
                if (document.hidden) { flush(); onScreen = false; startedAt = 0; }
            });
            window.addEventListener('pagehide', flush);
        }

        // Clicks: résumé links, patent records, social profiles.
        document.addEventListener('click', function (ev) {
            var a = ev.target.closest('a');
            if (!a) return;
            if (a.hash === '#resume' && a.hostname === location.hostname) {
                gtag('event', 'resume_link_click', { link_text: a.textContent.trim() });
            }
            if (a.classList.contains('resume-download-link') || /\/Soon-F-Hoo-Resume\.pdf$/.test(a.pathname)) {
                gtag('event', 'resume_download', {
                    link_location: a.getAttribute('data-link-location') || sectionOf(a),
                    transport_type: 'beacon'
                });
            }
            if (a.hostname === 'hoo.coffee' || a.hostname === 'www.hoo.coffee') {
                gtag('event', 'studio_click', {
                    link_url: a.href,
                    link_location: a.getAttribute('data-link-location') || sectionOf(a),
                    transport_type: 'beacon'
                });
            }
            if (a.hostname === 'patents.google.com' || a.hostname === 'patents.justia.com') {
                var card = a.closest('.patent-card');
                var title = card && card.querySelector('h3, h4');
                var label = card && card.querySelector('.eyebrow');
                var pid = (a.pathname.match(/patent\/([^/]+)/) || [])[1] || a.href;
                // Justia URLs carry only the number; use the card's "US 12,726,343 B1" label so IDs match Google's format.
                if (a.hostname === 'patents.justia.com' && label) pid = label.textContent.replace(/[\s,]/g, '');
                gtag('event', 'patent_click', {
                    patent_id: pid,
                    patent_source: a.hostname,
                    patent_title: title ? title.textContent.trim() : '',
                    transport_type: 'beacon'
                });
            }
            if (SOCIAL[a.hostname]) {
                gtag('event', 'social_click', {
                    network: SOCIAL[a.hostname],
                    link_section: sectionOf(a),
                    transport_type: 'beacon'
                });
            }
        });
    });
})();
