

class CustomAttributionControl extends maptilersdk.AttributionControl {
    constructor(options) {
        super(options);
        this.autoClose = options.autoClose !== false;
    }
    onAdd(map) {
        const container = super.onAdd(map);
        // Automatically close the AttributionControl if autoClose is enabled
        if (this.autoClose) {
            const attributionButton = container.querySelector('.maplibregl-ctrl-attrib-button');
            if (attributionButton) {
                attributionButton.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));
                container.classList.add('fade-in');
            }
        }
        return container;
    }
}

export { CustomAttributionControl };