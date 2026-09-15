(() => {
    const toggle = document.querySelector("#nav-toggle");
    const navigation = document.querySelector("#primary-navigation");
    const mobile = window.matchMedia("(max-width: 900px)");

    if (toggle && navigation) {
        const setOpen = (open, returnFocus = false) => {
            navigation.classList.toggle("is-open", open);
            document.body.classList.toggle("nav-open", open);
            toggle.setAttribute("aria-expanded", String(open));
            navigation.inert = mobile.matches && !open;
            if (returnFocus) toggle.focus();
        };

        const syncViewport = () => setOpen(false);

        toggle.addEventListener("click", () => {
            const open = toggle.getAttribute("aria-expanded") !== "true";
            setOpen(open);
            if (open) navigation.querySelector("a")?.focus();
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
                setOpen(false, true);
            }
        });
        navigation.addEventListener("click", (event) => {
            if (mobile.matches && event.target.closest("a")) setOpen(false);
        });
        mobile.addEventListener("change", syncViewport);
        syncViewport();
    }

    const errorSummary = document.querySelector("[data-error-summary]");
    if (errorSummary) errorSummary.focus();
})();
