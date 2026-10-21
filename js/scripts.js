const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#site-nav');
function closeMenu() {
    navigation.classList.remove('is-open');
    menuButton.setAttribute('aria-expanded', 'false');
}
menuButton.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!expanded));
    navigation.classList.toggle('is-open', !expanded);
});
navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navigation.classList.contains('is-open')) {
        closeMenu();
        menuButton.focus();
    }
});
if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            navigation.querySelectorAll('a').forEach(link => {
                if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
            });
        });
    }, { rootMargin: '-20% 0px -60% 0px' });
    document.querySelectorAll('main section[id]').forEach(section => observer.observe(section));
}
// Email link: the address is never in the page source. It is decoded only
// when a real person clicks or presses Enter, which keeps scrapers out.
document.querySelectorAll('.email-link[data-k]').forEach(link => {
    const reveal = event => {
        if (!event.isTrusted) return;
        event.preventDefault();
        const address = link.dataset.k.split('.').map(n => String.fromCharCode(Number(n) ^ 0x5a)).reverse().join('');
        if (window.gtag) window.gtag('event', 'email_click', { link_section: 'contact' });
        link.textContent = address;
        link.href = 'mail' + 'to:' + address;
        link.removeAttribute('data-k');
        window.location.href = link.href;
    };
    link.addEventListener('click', reveal, { once: true });
});
