// Google Analytics 4 tracking for sfhoo.com
(function () {
    var GA_ID = 'G-WQ2P9YBCG0'; 
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag('js', new Date());
    gtag('config', GA_ID);

    // Entry point: which section the visitor landed on and where they came from.
    // (GA4 also records landing page and traffic source automatically.)
    gtag('event', 'entry_point', {
        entry_section: location.hash ? location.hash.slice(1) : 'top',
        entry_referrer: document.referrer || '(direct)'
    });

    document.addEventListener('DOMContentLoaded', function () {
        // Résumé views: fire once when the résumé section is actually on screen.
        var resume = document.getElementById('resume');
        if (resume && 'IntersectionObserver' in window) {
            var seen = false;
            var obs = new IntersectionObserver(function (entries) {
                entries.forEach(function (e) {
                    if (e.isIntersecting && !seen) {
                        seen = true;
                        gtag('event', 'resume_view', { method: 'scroll' });
                        obs.disconnect();
                    }
                });
            }, { threshold: 0.25 });
            obs.observe(resume);
        }

        document.addEventListener('click', function (ev) {
            var a = ev.target.closest('a');
            if (!a) return;
            // Clicks on links that jump to the résumé
            if (a.hash === '#resume') {
                gtag('event', 'resume_link_click', { link_text: a.textContent.trim() });
            }
            // Clicks on patent grant records (Google Patents)
            if (a.hostname === 'patents.google.com') {
                var card = a.closest('.patent-card');
                var title = card && card.querySelector('h3, h4');
                gtag('event', 'patent_click', {
                    patent_id: (a.pathname.match(/patent\/([^/]+)/) || [])[1] || a.href,
                    patent_title: title ? title.textContent.trim() : '',
                    transport_type: 'beacon'
                });
            }
        });
    });
})();
